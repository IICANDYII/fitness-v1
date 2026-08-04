param(
  [string]$InputPath,

  [string]$InputJson,

  [string]$InputMarkdown,

  [string]$OutputDir = ".\outputs",

  [int]$DefaultAgeYears = 30,

  [ValidateSet("female", "male")]
  [string]$DefaultSex = "female",

  [Nullable[double]]$DefaultTargetKcal = $null
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($InputPath)) {
  if (-not [string]::IsNullOrWhiteSpace($InputJson)) {
    $InputPath = $InputJson
  }
  elseif (-not [string]::IsNullOrWhiteSpace($InputMarkdown)) {
    $InputPath = $InputMarkdown
  }
}

if ([string]::IsNullOrWhiteSpace($InputPath)) {
  throw "Provide -InputPath, -InputJson, or legacy -InputMarkdown."
}

function Round2([Nullable[double]]$value) {
  if ($null -eq $value) { return $null }
  return [Math]::Round([double]$value, 2)
}

function Round4([Nullable[double]]$value) {
  if ($null -eq $value) { return $null }
  return [Math]::Round([double]$value, 4)
}

function HasProperty($object, [string]$name) {
  return ($null -ne $object -and $null -ne $object.PSObject.Properties[$name])
}

function Get-FieldValue($object, [string]$name, [Nullable[double]]$default = 0.0) {
  if (-not (HasProperty $object $name)) { return $default }
  $raw = $object.$name
  if ($null -eq $raw) { return $default }
  return [double]$raw
}

function Get-EstimateValue($estimate, [Nullable[double]]$default = 0.0) {
  if ($null -eq $estimate) { return $default }
  if ($estimate -is [int] -or $estimate -is [long] -or $estimate -is [float] -or $estimate -is [double] -or $estimate -is [decimal]) {
    return [double]$estimate
  }
  if (HasProperty $estimate "value_mid") { return [double]$estimate.value_mid }
  if (HasProperty $estimate "value") { return [double]$estimate.value }
  if (HasProperty $estimate "value_range") {
    $range = @($estimate.value_range)
    if ($range.Count -ge 2) { return ([double]$range[0] + [double]$range[1]) / 2.0 }
  }
  return $default
}

function Get-RangeValue($object, [string]$midName, [string]$rangeName, [Nullable[double]]$default = 0.0) {
  if (HasProperty $object $midName) { return [double]$object.$midName }
  if (HasProperty $object $rangeName) {
    $range = @($object.$rangeName)
    if ($range.Count -ge 2) { return ([double]$range[0] + [double]$range[1]) / 2.0 }
  }
  return $default
}

function MacroRangeScore([double]$x, [double]$lower, [double]$upper, [double]$hardLow, [double]$hardHigh) {
  if ($x -ge $lower -and $x -le $upper) { return 100.0 }
  if ($x -ge $hardLow -and $x -lt $lower) { return 100.0 * ($x - $hardLow) / ($lower - $hardLow) }
  if ($x -gt $upper -and $x -le $hardHigh) { return 100.0 * ($hardHigh - $x) / ($hardHigh - $upper) }
  return 0.0
}

function AdequacyScore([double]$ratio) {
  if ($ratio -ge 1.0) { return 100.0 }
  if ($ratio -ge 0.8) { return 80.0 + (($ratio - 0.8) / 0.2 * 20.0) }
  if ($ratio -ge 0.5) { return 40.0 + (($ratio - 0.5) / 0.3 * 40.0) }
  return $ratio / 0.5 * 40.0
}

function KcalBalanceScore([double]$actualKcal, [double]$targetKcal) {
  if ($actualKcal -le 0) { throw "actual kcal must be greater than zero for Kcal Balance scoring." }
  if ($targetKcal -le 0) { throw "target kcal must be greater than zero for Kcal Balance scoring." }

  $ratio = $actualKcal / $targetKcal
  $deviation = [Math]::Abs($ratio - 1.0)

  if ($deviation -le 0.10) { $score = 100.0 }
  elseif ($deviation -ge 0.50) { $score = 0.0 }
  else { $score = 100.0 * (0.50 - $deviation) / 0.40 }

  return [pscustomobject][ordered]@{
    included_in_diet_balance = $true
    actual_kcal = Round2 $actualKcal
    target_kcal = Round2 $targetKcal
    actual_to_target_ratio = Round4 $ratio
    deviation_from_target = Round4 $deviation
    full_score_band = "0.90-1.10 of target_kcal"
    zero_score_at_or_beyond = "<=0.50 or >=1.50 of target_kcal"
    score = Round2 $score
  }
}

function Get-KcalTarget($user) {
  $candidateNames = @(
    "target_kcal",
    "tdee_kcal",
    "estimated_energy_requirement_kcal",
    "energy_requirement_kcal",
    "energy_need_kcal",
    "recommended_kcal"
  )

  foreach ($name in $candidateNames) {
    if (HasProperty $user.daily_total $name -and $null -ne $user.daily_total.$name) {
      return [pscustomobject][ordered]@{
        available = $true
        value = [double]$user.daily_total.$name
        source = "daily_total.$name"
      }
    }
    if (HasProperty $user $name -and $null -ne $user.$name) {
      return [pscustomobject][ordered]@{
        available = $true
        value = [double]$user.$name
        source = $name
      }
    }
  }

  if ($null -ne $DefaultTargetKcal) {
    return [pscustomobject][ordered]@{
      available = $true
      value = [double]$DefaultTargetKcal
      source = "DefaultTargetKcal parameter"
    }
  }

  return [pscustomobject][ordered]@{
    available = $false
    value = $null
    source = "unavailable"
  }
}

function NormalizeSex([string]$sex) {
  if ([string]::IsNullOrWhiteSpace($sex)) { return $DefaultSex }
  $normalized = $sex.ToLowerInvariant()
  if ($normalized -in @("male", "m", "man")) { return "male" }
  if ($normalized -in @("female", "f", "woman")) { return "female" }
  return $DefaultSex
}

function Get-UserProfileForScoring($user) {
  $profile = if (HasProperty $user "user_profile") { $user.user_profile } else { $null }

  $age = $DefaultAgeYears
  if (HasProperty $profile "age_years" -and $null -ne $profile.age_years) {
    $age = [int]$profile.age_years
  }
  elseif (HasProperty $user "age_years" -and $null -ne $user.age_years) {
    $age = [int]$user.age_years
  }

  $sex = $DefaultSex
  if (HasProperty $profile "sex" -and $null -ne $profile.sex) {
    $sex = NormalizeSex ([string]$profile.sex)
  }
  elseif (HasProperty $user "sex" -and $null -ne $user.sex) {
    $sex = NormalizeSex ([string]$user.sex)
  }

  $weightKg = $null
  if (HasProperty $profile "weight_kg" -and $null -ne $profile.weight_kg) {
    $weightKg = [double]$profile.weight_kg
  }
  elseif (HasProperty $user "weight_kg" -and $null -ne $user.weight_kg) {
    $weightKg = [double]$user.weight_kg
  }

  return [pscustomobject][ordered]@{
    age_years = $age
    sex = $sex
    weight_kg = $weightKg
    source = if ($null -ne $profile) { "user_profile" } else { "calculator_defaults_or_user_root" }
  }
}

function AddIfMatch([string]$text, [string]$pattern, [double]$amount) {
  if ($text -match $pattern) { return $amount }
  return 0.0
}

function New-FoodGroupTotals([string]$source) {
  return [pscustomobject][ordered]@{
    total_fruits_cup = 0.0
    whole_fruits_cup = 0.0
    fruit_juice_cup = 0.0
    total_vegetables_cup = 0.0
    greens_and_beans_cup = 0.0
    whole_grains_oz = 0.0
    refined_grains_oz = 0.0
    dairy_cup = 0.0
    total_protein_foods_oz = 0.0
    seafood_and_plant_proteins_oz = 0.0
    fiber_g = 0.0
    input_source = $source
    structured_food_groups_available = $false
    full_day_record_complete = $false
  }
}

function Add-FoodGroupEstimate($totals, $estimates) {
  if ($null -eq $estimates) { return }
  $totals.total_fruits_cup += Get-EstimateValue $estimates.total_fruits_cup
  $totals.whole_fruits_cup += Get-EstimateValue $estimates.whole_fruits_cup
  $totals.fruit_juice_cup += Get-EstimateValue $estimates.fruit_juice_cup
  $totals.total_vegetables_cup += Get-EstimateValue $estimates.total_vegetables_cup
  $totals.greens_and_beans_cup += Get-EstimateValue $estimates.greens_and_beans_cup
  $totals.whole_grains_oz += Get-EstimateValue $estimates.whole_grains_oz
  $totals.refined_grains_oz += Get-EstimateValue $estimates.refined_grains_oz
  $totals.dairy_cup += Get-EstimateValue $estimates.dairy_cup
  $totals.total_protein_foods_oz += Get-EstimateValue $estimates.total_protein_foods_oz
  $totals.seafood_and_plant_proteins_oz += Get-EstimateValue $estimates.seafood_and_plant_proteins_oz
  $totals.fiber_g += Get-EstimateValue $estimates.fiber_g
}

function Convert-V2FoodGroupTotals($user) {
  $totals = New-FoodGroupTotals "none"
  $daily = $user.daily_total

  if (HasProperty $daily "food_group_totals") {
    $fg = $daily.food_group_totals
    $totals.total_fruits_cup = Get-FieldValue $fg "total_fruits_cup"
    $totals.whole_fruits_cup = Get-FieldValue $fg "whole_fruits_cup"
    $totals.fruit_juice_cup = Get-FieldValue $fg "fruit_juice_cup"
    $totals.total_vegetables_cup = Get-FieldValue $fg "total_vegetables_cup"
    $totals.greens_and_beans_cup = Get-FieldValue $fg "greens_and_beans_cup"
    $totals.whole_grains_oz = Get-FieldValue $fg "whole_grains_oz"
    $totals.refined_grains_oz = Get-FieldValue $fg "refined_grains_oz"
    $totals.dairy_cup = Get-FieldValue $fg "dairy_cup"
    $totals.total_protein_foods_oz = Get-FieldValue $fg "total_protein_foods_oz"
    $totals.seafood_and_plant_proteins_oz = Get-FieldValue $fg "seafood_and_plant_proteins_oz"
    $totals.fiber_g = Get-RangeValue $fg "fiber_g_mid" "fiber_g_range" (Get-FieldValue $fg "fiber_g")
    $totals.input_source = "daily_total.food_group_totals"
    $totals.structured_food_groups_available = $true
  }
  elseif ($null -ne $user.meals) {
    foreach ($meal in $user.meals) {
      if (HasProperty $meal "food_group_estimates") {
        Add-FoodGroupEstimate $totals $meal.food_group_estimates
        $totals.structured_food_groups_available = $true
      }
    }
    if ($totals.structured_food_groups_available) {
      $totals.input_source = "sum(meals.food_group_estimates)"
    }
  }

  if (HasProperty $daily "coverage_flags") {
    $flags = $daily.coverage_flags
    if (HasProperty $flags "full_day_record_complete") {
      $totals.full_day_record_complete = [bool]$flags.full_day_record_complete
    }
  }
  elseif ((Get-FieldValue $daily "available_meals") -ge 3) {
    $totals.full_day_record_complete = $true
  }

  return $totals
}

function Get-HeiComponentInclusion($user, $groups) {
  $include = [ordered]@{
    total_fruits = $false
    whole_fruits = $false
    total_vegetables = $false
    greens_and_beans = $false
    whole_grains = $false
    dairy = $false
    total_protein_foods = $false
    seafood_and_plant_proteins = $false
    refined_grains = $false
  }

  if ($groups.full_day_record_complete) {
    foreach ($key in @($include.Keys)) {
      $include[$key] = $true
    }
    return [pscustomobject]$include
  }

  foreach ($meal in @($user.meals)) {
    if (-not (HasProperty $meal "food_group_estimates")) { continue }
    $estimates = $meal.food_group_estimates
    if (HasProperty $estimates "total_fruits_cup") { $include["total_fruits"] = $true }
    if (HasProperty $estimates "whole_fruits_cup") { $include["whole_fruits"] = $true }
    if (HasProperty $estimates "total_vegetables_cup") { $include["total_vegetables"] = $true }
    if (HasProperty $estimates "greens_and_beans_cup") { $include["greens_and_beans"] = $true }
    if (HasProperty $estimates "whole_grains_oz") { $include["whole_grains"] = $true }
    if (HasProperty $estimates "dairy_cup") { $include["dairy"] = $true }
    if (HasProperty $estimates "total_protein_foods_oz") { $include["total_protein_foods"] = $true }
    if (HasProperty $estimates "seafood_and_plant_proteins_oz") { $include["seafood_and_plant_proteins"] = $true }
    if (HasProperty $estimates "refined_grains_oz") { $include["refined_grains"] = $true }
  }

  return [pscustomobject]$include
}

function EstimateFoodGroupsFromNames($meals) {
  $g = New-FoodGroupTotals "legacy_food_name_keyword_fallback"

  foreach ($meal in $meals) {
    foreach ($food in $meal.foods) {
      $t = ([string]$food).ToLowerInvariant()

      $wholeGrain = 0.0
      $wholeGrain += AddIfMatch $t "brown rice|oats|whole wheat|whole grain bread|quinoa|barley|whole grain cereal" 1.5
      if ($wholeGrain -gt 0) {
        $g.whole_grains_oz += $wholeGrain
        $g.fiber_g += $wholeGrain * 2.0
      }

      $refined = 0.0
      $refined += AddIfMatch $t "fried rice|white rice|steamed white rice|rice bowl|with rice|rice and" 2.0
      $refined += AddIfMatch $t "noodle|noodles|rice noodle|rice rolls|cheung fun" 2.5
      $refined += AddIfMatch $t "bun|baozi|jianbing|crepe|toast|waffle|corn dog|wonton|congee|pizza|burger|fries|white bread" 1.5
      if ($refined -gt 0) {
        $g.refined_grains_oz += $refined
        $g.fiber_g += $refined * 0.3
      }

      $veg = 0.0
      $greens = 0.0
      $veg += AddIfMatch $t "vegetable|vegetables|broccoli|cabbage|spinach|bok choy|lettuce|cauliflower|pepper|chili|potato|celery|bamboo shoot|wood ear|seaweed|greens|leafy|salad" 0.5
      $veg += AddIfMatch $t "broccoli|cabbage|spinach|bok choy|lettuce|cauliflower|celery|leafy|greens" 0.25
      $greens += AddIfMatch $t "spinach|bok choy|lettuce|cabbage|leafy|greens|seaweed|beans|red bean" 0.5
      if ($veg -gt 0) {
        $g.total_vegetables_cup += $veg
        $g.greens_and_beans_cup += $greens
        $g.fiber_g += $veg * 2.5
      }

      $fruit = 0.0
      $fruit += AddIfMatch $t "apple slice|fruit garnish" 0.1
      if ($fruit -eq 0.0) {
        $fruit += AddIfMatch $t "apple|grapefruit|citrus|orange|pineapple|berries|banana|fruit" 0.5
      }
      if ($fruit -gt 0) {
        $g.total_fruits_cup += $fruit
        $g.whole_fruits_cup += $fruit
        $g.fiber_g += $fruit * 3.0
      }

      $juice = AddIfMatch $t "juice|fruit drink" 0.5
      if ($juice -gt 0) {
        $g.total_fruits_cup += $juice
        $g.fruit_juice_cup += $juice
      }

      $protein = 0.0
      $plantSeafood = 0.0
      $protein += AddIfMatch $t "steak|beef steak" 5.0
      $protein += AddIfMatch $t "beef|pork|chicken|meat|egg|tofu|shrimp|squid|fish|wonton|peanut|beans|red bean|bacon" 2.0
      $protein += AddIfMatch $t "egg" 1.0
      $plantSeafood += AddIfMatch $t "tofu|shrimp|squid|fish|peanut|beans|red bean" 2.0
      if ($protein -gt 0) {
        $g.total_protein_foods_oz += $protein
        $g.seafood_and_plant_proteins_oz += $plantSeafood
      }

      if ($t -notmatch "soy milk") {
        $dairy = AddIfMatch $t "cream cheese|cheese|milk|yogurt|dairy drink|cream" 0.25
        if ($dairy -gt 0) { $g.dairy_cup += $dairy }
      }
    }
  }

  $g.full_day_record_complete = $true
  return $g
}

function CleanCell([string]$cell) {
  return (($cell -replace "\*\*", "") -replace "\\\|", "|").Trim()
}

function SplitMarkdownRow([string]$line) {
  $trimmed = $line.Trim()
  if (-not $trimmed.StartsWith("|")) { return @() }
  $inner = $trimmed.Trim("|")
  return @($inner -split "\|" | ForEach-Object { CleanCell $_ })
}

function ParseNutritionSummaryMarkdown([string]$path) {
  $lines = Get-Content -LiteralPath $path -Encoding UTF8
  $users = [ordered]@{}
  $currentUserId = $null

  foreach ($line in $lines) {
    if ($line -match "^###\s+(user[0-9]+-[0-9]+)\b(.*)$") {
      $currentUserId = $Matches[1]
      $headingTail = ($Matches[2] -replace "^[\s-]+", "").Trim()
      if (-not $users.Contains($currentUserId)) {
        $users[$currentUserId] = [ordered]@{
          user_id = $currentUserId
          profile = $headingTail
          meals = @()
          daily_total = $null
        }
      }
      elseif ([string]::IsNullOrWhiteSpace([string]$users[$currentUserId].profile)) {
        $users[$currentUserId].profile = $headingTail
      }
      continue
    }

    $cells = SplitMarkdownRow $line
    if ($cells.Count -lt 5) { continue }
    if ($cells[0] -in @("---", "用户", "餐次")) { continue }

    if ($cells[0] -match "^user[0-9]+-[0-9]+$" -and $cells.Count -ge 7) {
      $userId = $cells[0]
      $profile = $cells[1]
      $kcalText = $cells[5]
      $macroText = $cells[6]
      $kcalMatch = [regex]::Match($kcalText, "([0-9]+(?:\.[0-9]+)?)\s*\(([0-9]+(?:\.[0-9]+)?)-([0-9]+(?:\.[0-9]+)?)\)")
      $macroMatch = [regex]::Match($macroText, "([0-9]+(?:\.[0-9]+)?)%\s*/\s*([0-9]+(?:\.[0-9]+)?)%\s*/\s*([0-9]+(?:\.[0-9]+)?)%")
      if ($kcalMatch.Success -and $macroMatch.Success) {
        if (-not $users.Contains($userId)) {
          $users[$userId] = [ordered]@{
            user_id = $userId
            profile = $profile
            meals = @()
            daily_total = $null
          }
        }
        $users[$userId].daily_total = [ordered]@{
          available_meals = $users[$userId].meals.Count
          kcal_mid = [double]$kcalMatch.Groups[1].Value
          kcal_range = @([double]$kcalMatch.Groups[2].Value, [double]$kcalMatch.Groups[3].Value)
          macro_structure_pct = [ordered]@{
            protein = [double]$macroMatch.Groups[1].Value
            fat = [double]$macroMatch.Groups[2].Value
            carb = [double]$macroMatch.Groups[3].Value
          }
        }
      }
      continue
    }

    if ($null -ne $currentUserId -and $cells.Count -ge 5 -and $cells[0] -notmatch "^全天$") {
      $slot = $cells[0]
      $foodsText = $cells[1]
      $kcalRangeText = $cells[2]
      $kcalMidText = $cells[3]
      $macroText = $cells[4]

      $kcalRangeMatch = [regex]::Match($kcalRangeText, "([0-9]+(?:\.[0-9]+)?)-([0-9]+(?:\.[0-9]+)?)")
      $mealMacroMatch = [regex]::Match($macroText, "([0-9]+(?:\.[0-9]+)?)%\s*/\s*([0-9]+(?:\.[0-9]+)?)%\s*/\s*([0-9]+(?:\.[0-9]+)?)%")
      if ($kcalRangeMatch.Success -and $mealMacroMatch.Success) {
        $foods = @($foodsText -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ })
        $users[$currentUserId].meals += [pscustomobject][ordered]@{
          meal_slot = $slot
          foods = $foods
          kcal_range = @([double]$kcalRangeMatch.Groups[1].Value, [double]$kcalRangeMatch.Groups[2].Value)
          kcal_mid = [double]$kcalMidText
          macro_structure_pct = [ordered]@{
            protein = [double]$mealMacroMatch.Groups[1].Value
            fat = [double]$mealMacroMatch.Groups[2].Value
            carb = [double]$mealMacroMatch.Groups[3].Value
          }
        }
      }
    }
  }

  return @($users.Values | ForEach-Object { [pscustomobject]$_ })
}

function ParseNutritionJson([string]$path) {
  $payload = Get-Content -Raw -LiteralPath $path -Encoding UTF8 | ConvertFrom-Json
  return @($payload.users)
}

function HeiAdequacyComponent([string]$name, [double]$value, [double]$standard, [double]$maxPoints) {
  $score = [Math]::Min($maxPoints, ($value / $standard) * $maxPoints)
  return [pscustomobject]@{
    name = $name
    type = "adequacy"
    value = Round4 $value
    standard_for_max = $standard
    score = Round2 $score
    max_points = $maxPoints
  }
}

function HeiModerationComponent([string]$name, [double]$value, [double]$best, [double]$zero, [double]$maxPoints) {
  if ($value -le $best) { $score = $maxPoints }
  elseif ($value -ge $zero) { $score = 0.0 }
  else { $score = $maxPoints * ($zero - $value) / ($zero - $best) }
  return [pscustomObject]@{
    name = $name
    type = "moderation"
    value = Round4 $value
    standard_for_max_or_less = $best
    standard_for_zero_or_more = $zero
    score = Round2 $score
    max_points = $maxPoints
  }
}

function HeiFattyAcidsComponent([double]$ratio, [double]$zero, [double]$best, [double]$maxPoints) {
  if ($ratio -ge $best) { $score = $maxPoints }
  elseif ($ratio -le $zero) { $score = 0.0 }
  else { $score = $maxPoints * ($ratio - $zero) / ($best - $zero) }
  return [pscustomObject]@{
    name = "fatty_acids"
    type = "adequacy"
    value = Round4 $ratio
    standard_for_zero_or_less = $zero
    standard_for_max_or_more = $best
    score = Round2 $score
    max_points = $maxPoints
  }
}

function AddHeiComponentIfIncluded([object[]]$components, $include, [string]$key, $component) {
  if ($include.$key) { return @($components + $component) }
  return $components
}

function Get-ModerationField($moderation, [string]$name) {
  if ($null -eq $moderation -or -not (HasProperty $moderation $name)) {
    return [pscustomobject][ordered]@{ exists = $false; value = $null; confidence = $null; source = "missing" }
  }

  $raw = $moderation.$name
  if ($null -eq $raw) {
    return [pscustomobject][ordered]@{ exists = $false; value = $null; confidence = $null; source = "null" }
  }

  $value = Get-EstimateValue $raw $null
  $confidence = if (HasProperty $raw "confidence") { [string]$raw.confidence } else { $null }
  return [pscustomobject][ordered]@{
    exists = $true
    value = [double]$value
    confidence = $confidence
    source = "daily_total.moderation_estimates.$name"
  }
}

function Get-FattyAcidsField($moderation) {
  if ($null -eq $moderation -or -not (HasProperty $moderation "fatty_acids")) {
    return [pscustomobject][ordered]@{ exists = $false; ratio = $null; confidence = $null; pufa_g = $null; mufa_g = $null; sfa_g = $null; source = "missing" }
  }

  $raw = $moderation.fatty_acids
  if ($null -eq $raw) {
    return [pscustomobject][ordered]@{ exists = $false; ratio = $null; confidence = $null; pufa_g = $null; mufa_g = $null; sfa_g = $null; source = "null" }
  }

  $pufa = if (HasProperty $raw "pufa_g") { [double]$raw.pufa_g } else { $null }
  $mufa = if (HasProperty $raw "mufa_g") { [double]$raw.mufa_g } else { $null }
  $sfa = if (HasProperty $raw "sfa_g") { [double]$raw.sfa_g } elseif (HasProperty $raw "saturated_fat_g") { [double]$raw.saturated_fat_g } else { $null }
  $ratio = $null
  if (HasProperty $raw "ratio_pufa_mufa_over_sfa" -and $null -ne $raw.ratio_pufa_mufa_over_sfa) {
    $ratio = [double]$raw.ratio_pufa_mufa_over_sfa
  }
  elseif ($null -ne $pufa -and $null -ne $mufa -and $null -ne $sfa -and $sfa -gt 0) {
    $ratio = ($pufa + $mufa) / $sfa
  }

  if ($null -eq $ratio) {
    return [pscustomobject][ordered]@{ exists = $false; ratio = $null; confidence = $null; pufa_g = $pufa; mufa_g = $mufa; sfa_g = $sfa; source = "insufficient_fatty_acids_fields" }
  }

  return [pscustomobject][ordered]@{
    exists = $true
    ratio = [double]$ratio
    confidence = if (HasProperty $raw "confidence") { [string]$raw.confidence } else { $null }
    pufa_g = $pufa
    mufa_g = $mufa
    sfa_g = $sfa
    source = "daily_total.moderation_estimates.fatty_acids"
  }
}

function Add-ComponentDebug($component, $debugInfo) {
  if ($null -eq $component) { return $null }
  $component | Add-Member -NotePropertyName input_debug -NotePropertyValue $debugInfo -Force
  return $component
}

function CalculateHeiAvailable($groups, [double]$kcal, $include, $moderation) {
  if ($kcal -le 0) { throw "kcal_mid must be greater than zero for HEI density scoring." }
  $per1000 = $kcal / 1000.0
  $components = @()

  $components = AddHeiComponentIfIncluded $components $include "total_fruits" (HeiAdequacyComponent "total_fruits" ($groups.total_fruits_cup / $per1000) 0.8 5.0)
  $components = AddHeiComponentIfIncluded $components $include "whole_fruits" (HeiAdequacyComponent "whole_fruits" ($groups.whole_fruits_cup / $per1000) 0.4 5.0)
  $components = AddHeiComponentIfIncluded $components $include "total_vegetables" (HeiAdequacyComponent "total_vegetables" ($groups.total_vegetables_cup / $per1000) 1.1 5.0)
  $components = AddHeiComponentIfIncluded $components $include "greens_and_beans" (HeiAdequacyComponent "greens_and_beans" ($groups.greens_and_beans_cup / $per1000) 0.2 5.0)
  $components = AddHeiComponentIfIncluded $components $include "whole_grains" (HeiAdequacyComponent "whole_grains" ($groups.whole_grains_oz / $per1000) 1.5 10.0)
  $components = AddHeiComponentIfIncluded $components $include "dairy" (HeiAdequacyComponent "dairy" ($groups.dairy_cup / $per1000) 1.3 10.0)
  $components = AddHeiComponentIfIncluded $components $include "total_protein_foods" (HeiAdequacyComponent "total_protein_foods" ($groups.total_protein_foods_oz / $per1000) 2.5 5.0)
  $components = AddHeiComponentIfIncluded $components $include "seafood_and_plant_proteins" (HeiAdequacyComponent "seafood_and_plant_proteins" ($groups.seafood_and_plant_proteins_oz / $per1000) 0.8 5.0)
  $components = AddHeiComponentIfIncluded $components $include "refined_grains" (HeiModerationComponent "refined_grains" ($groups.refined_grains_oz / $per1000) 1.8 4.3 10.0)

  $moderationDebug = [ordered]@{}

  $satFat = Get-ModerationField $moderation "saturated_fat_g"
  $moderationDebug.saturated_fat_g = $satFat
  if ($satFat.exists) {
    $satFatPctEnergy = ([double]$satFat.value * 9.0 / $kcal) * 100.0
    $component = HeiModerationComponent "saturated_fats" $satFatPctEnergy 8.0 16.0 10.0
    $component = Add-ComponentDebug $component ([pscustomobject][ordered]@{
      input_value_g = Round2 $satFat.value
      converted_percent_energy = Round4 $satFatPctEnergy
      confidence = $satFat.confidence
      source = $satFat.source
    })
    $components += $component
  }

  $addedSugars = Get-ModerationField $moderation "added_sugars_g"
  $moderationDebug.added_sugars_g = $addedSugars
  if ($addedSugars.exists) {
    $addedSugarsPctEnergy = ([double]$addedSugars.value * 4.0 / $kcal) * 100.0
    $component = HeiModerationComponent "added_sugars" $addedSugarsPctEnergy 6.5 26.0 10.0
    $component = Add-ComponentDebug $component ([pscustomobject][ordered]@{
      input_value_g = Round2 $addedSugars.value
      converted_percent_energy = Round4 $addedSugarsPctEnergy
      confidence = $addedSugars.confidence
      source = $addedSugars.source
    })
    $components += $component
  }

  $sodium = Get-ModerationField $moderation "sodium_mg"
  $moderationDebug.sodium_mg = $sodium
  if ($sodium.exists) {
    $sodiumGPer1000Kcal = [double]$sodium.value / $kcal
    $component = HeiModerationComponent "sodium" $sodiumGPer1000Kcal 1.1 2.0 10.0
    $component = Add-ComponentDebug $component ([pscustomobject][ordered]@{
      input_value_mg = Round2 $sodium.value
      converted_g_per_1000kcal = Round4 $sodiumGPer1000Kcal
      confidence = $sodium.confidence
      source = $sodium.source
    })
    $components += $component
  }

  $fattyAcids = Get-FattyAcidsField $moderation
  $moderationDebug.fatty_acids = $fattyAcids
  if ($fattyAcids.exists) {
    $component = HeiFattyAcidsComponent ([double]$fattyAcids.ratio) 1.2 2.5 10.0
    $component = Add-ComponentDebug $component ([pscustomobject][ordered]@{
      ratio_pufa_mufa_over_sfa = Round4 $fattyAcids.ratio
      pufa_g = Round2 $fattyAcids.pufa_g
      mufa_g = Round2 $fattyAcids.mufa_g
      sfa_g = Round2 $fattyAcids.sfa_g
      confidence = $fattyAcids.confidence
      source = $fattyAcids.source
    })
    $components += $component
  }

  $score = 0.0
  $max = 0.0
  foreach ($component in $components) {
    $score += [double]$component.score
    $max += [double]$component.max_points
  }

  $scoredNames = @($components | ForEach-Object { $_.name })
  $allModerationNames = @("fatty_acids", "sodium", "added_sugars", "saturated_fats")
  $unscored = @($allModerationNames | Where-Object { $_ -notin $scoredNames })

  return [pscustomobject]@{
    hei_2020_available = if ($max -gt 0) { Round2 (($score / $max) * 100.0) } else { 0.0 }
    recognized_score_points = Round2 $score
    recognized_max_points = Round2 $max
    components = $components
    unscored_components = $unscored
    moderation_estimates_used = $moderationDebug
    food_group_totals_used = $groups
    included_components = $include
  }
}

function CalculateRdaExplanation([double]$proteinG, [double]$fiberG, [int]$age, [string]$sex, [Nullable[double]]$weightKg) {
  if ([string]::IsNullOrWhiteSpace($sex)) { $sex = "female" }
  if ($age -le 0) { $age = 30 }

  $proteinTarget = if ($null -ne $weightKg -and $weightKg -gt 0) { 0.8 * [double]$weightKg } elseif ($sex -eq "male") { 56.0 } else { 46.0 }
  $proteinTargetSource = if ($null -ne $weightKg -and $weightKg -gt 0) { "0.8 g/kg/day from user weight" } else { "sex-based adult fallback" }
  if ($sex -eq "male") {
    $fiberTarget = if ($age -gt 50) { 30.0 } else { 38.0 }
  }
  else {
    $fiberTarget = if ($age -gt 50) { 21.0 } else { 25.0 }
  }

  $proteinRatio = $proteinG / $proteinTarget
  $fiberRatio = $fiberG / $fiberTarget

  $proteinScore = AdequacyScore $proteinRatio
  $fiberScore = AdequacyScore $fiberRatio
  $rdaAiAdequacy = (($proteinScore * 0.20) + ($fiberScore * 0.20)) / 0.40

  return [pscustomobject]@{
    included_in_diet_balance = $true
    note = "Protein is derived from kcal_mid and macro protein percentage. Protein target uses user weight when available (0.8 g/kg/day), otherwise sex-based adult fallback. Fiber target uses user age and sex. Fiber intake is read from structured fields when available, otherwise estimated by the legacy fallback."
    rda_ai_adequacy_partial = Round2 $rdaAiAdequacy
    recognized_weight_sum = 0.40
    user_profile_used = [pscustomobject]@{
      age_years = $age
      sex = $sex
      weight_kg = Round2 $weightKg
    }
    protein = [pscustomobject]@{
      actual_g = Round2 $proteinG
      target_g = Round2 $proteinTarget
      target_source = $proteinTargetSource
      ratio = Round4 $proteinRatio
      score = Round2 $proteinScore
      weight = 0.20
    }
    fiber = [pscustomobject]@{
      actual_g = Round2 $fiberG
      target_g = $fiberTarget
      ratio = Round4 $fiberRatio
      score = Round2 $fiberScore
      weight = 0.20
    }
  }
}

function BuildUserResult($user) {
  if ($null -eq $user.daily_total) { return $null }

  $kcalMid = [double]$user.daily_total.kcal_mid
  $carbPct = [double]$user.daily_total.macro_structure_pct.carb / 100.0
  $fatPct = [double]$user.daily_total.macro_structure_pct.fat / 100.0
  $proteinPct = [double]$user.daily_total.macro_structure_pct.protein / 100.0
  $proteinG = ($kcalMid * $proteinPct) / 4.0
  $scoringProfile = Get-UserProfileForScoring $user

  $groups = Convert-V2FoodGroupTotals $user
  if (-not $groups.structured_food_groups_available) {
    $groups = EstimateFoodGroupsFromNames $user.meals
  }

  $isCompleteRecord = [bool]$groups.full_day_record_complete
  $rankingStatus = if ($isCompleteRecord) { "ranked" } else { "not_ranked" }
  $moderation = if (HasProperty $user.daily_total "moderation_estimates") { $user.daily_total.moderation_estimates } else { $null }
  $heiInclusion = Get-HeiComponentInclusion $user $groups
  $hei = CalculateHeiAvailable $groups $kcalMid $heiInclusion $moderation
  $carbScore = MacroRangeScore $carbPct 0.45 0.65 0.25 0.80
  $fatScore = MacroRangeScore $fatPct 0.20 0.35 0.10 0.50
  $proteinMacroScore = MacroRangeScore $proteinPct 0.10 0.35 0.05 0.45
  $amdrFit = ($carbScore * 0.40) + ($fatScore * 0.30) + ($proteinMacroScore * 0.30)
  $rda = CalculateRdaExplanation $proteinG ([double]$groups.fiber_g) ([int]$scoringProfile.age_years) ([string]$scoringProfile.sex) $scoringProfile.weight_kg
  $mealTiming = 100.0
  $kcalTarget = Get-KcalTarget $user
  $kcalBalance = if ($isCompleteRecord -and $kcalTarget.available) { KcalBalanceScore $kcalMid ([double]$kcalTarget.value) } else { $null }
  $dietBalance = if ($isCompleteRecord -and $null -ne $kcalBalance) {
    ([double]$hei.hei_2020_available * 0.40) + ($amdrFit * 0.15) + ([double]$rda.rda_ai_adequacy_partial * 0.20) + ($mealTiming * 0.10) + ([double]$kcalBalance.score * 0.15)
  }
  else {
    $null
  }
  $legacyReferenceBalance = ([double]$hei.hei_2020_available * 0.50) + ($amdrFit * 0.20) + ([double]$rda.rda_ai_adequacy_partial * 0.20) + ($mealTiming * 0.10)
  $partialWithoutKcalReference = ([double]$hei.hei_2020_available * 0.40) + ($amdrFit * 0.15) + ([double]$rda.rda_ai_adequacy_partial * 0.20) + ($mealTiming * 0.10)
  $structureScore = ((([double]$hei.hei_2020_available * 0.40) + ($amdrFit * 0.15)) / 0.55)
  $scoreStatus = if (-not $isCompleteRecord) {
    "incomplete_partial_day"
  }
  elseif ($null -eq $kcalBalance) {
    "kcal_target_unavailable"
  }
  else {
    "complete_with_kcal_balance"
  }

  return [pscustomobject][ordered]@{
    user_id = $user.user_id
    profile = $user.profile
    default_age_years = $DefaultAgeYears
    default_sex = $DefaultSex
    default_target_kcal = $DefaultTargetKcal
    scoring_profile = $scoringProfile
    diet_balance = if ($null -ne $dietBalance) { [Math]::Round($dietBalance, 0) } else { $null }
    diet_balance_raw = Round2 $dietBalance
    score_status = $scoreStatus
    ranking_status = $rankingStatus
    is_partial_day_score = -not $isCompleteRecord
    balance_method = "0.40*HEI_2020_available + 0.15*AMDR_Fit + 0.20*RDA_AI_Adequacy + 0.10*Meal_Timing + 0.15*Kcal_Balance"
    legacy_four_component_reference_raw = Round2 $legacyReferenceBalance
    partial_without_kcal_reference_raw = if (-not $isCompleteRecord) { Round2 $partialWithoutKcalReference } else { $null }
    abstract_scores = [ordered]@{
      structure = Round2 $structureScore
      nutrients = $rda.rda_ai_adequacy_partial
      rhythm = Round2 $mealTiming
      energy = if ($null -ne $kcalBalance) { $kcalBalance.score } else { $null }
    }
    components = [ordered]@{
      hei_2020_available = $hei.hei_2020_available
      amdr_fit = Round2 $amdrFit
      rda_ai_adequacy = $rda.rda_ai_adequacy_partial
      meal_timing = Round2 $mealTiming
      kcal_balance = if ($null -ne $kcalBalance) { $kcalBalance.score } else { $null }
    }
    contributions = [ordered]@{
      hei_2020_available = Round2 ([double]$hei.hei_2020_available * 0.40)
      amdr_fit = Round2 ($amdrFit * 0.15)
      rda_ai_adequacy = Round2 ([double]$rda.rda_ai_adequacy_partial * 0.20)
      meal_timing = Round2 ($mealTiming * 0.10)
      kcal_balance = if ($null -ne $kcalBalance) { Round2 ([double]$kcalBalance.score * 0.15) } else { $null }
    }
    debug = [ordered]@{
      amdr = [ordered]@{
        included_in_diet_balance = $true
        carb_pct = Round4 $carbPct
        fat_pct = Round4 $fatPct
        protein_pct = Round4 $proteinPct
        carb_score = Round2 $carbScore
        fat_score = Round2 $fatScore
        protein_score = Round2 $proteinMacroScore
      }
      hei_2020_available = $hei
      rda_ai_partial = $rda
      user_profile_source = $scoringProfile.source
      kcal_balance = if ($null -ne $kcalBalance) { $kcalBalance } else {
        [ordered]@{
          included_in_diet_balance = $false
          score = $null
          target_kcal = if ($kcalTarget.available) { Round2 ([double]$kcalTarget.value) } else { $null }
          target_source = $kcalTarget.source
          reason = if (-not $isCompleteRecord) { "missing_meals" } else { "target_kcal_unavailable" }
          note = if (-not $isCompleteRecord) { "Kcal Balance is not calculated for incomplete partial-day records because missing meals would make kcal intake misleading." } else { "Kcal Balance requires target_kcal, tdee_kcal, estimated_energy_requirement_kcal, energy_requirement_kcal, energy_need_kcal, recommended_kcal, or -DefaultTargetKcal." }
        }
      }
      kcal_target_source = $kcalTarget.source
      coverage_flags = if (HasProperty $user.daily_total "coverage_flags") { $user.daily_total.coverage_flags } else { $null }
      ranked = $isCompleteRecord
      food_group_input_source = $groups.input_source
      meal_timing_policy = "temporary_full_score_until_reliable_multi_day_timing_data"
    }
  }
}

$resolvedInput = (Resolve-Path -LiteralPath $InputPath).Path
$extension = [IO.Path]::GetExtension($resolvedInput).ToLowerInvariant()

if ($extension -eq ".json") {
  $parsedUsers = ParseNutritionJson $resolvedInput
  $sourceKind = "json"
}
else {
  $parsedUsers = ParseNutritionSummaryMarkdown $resolvedInput
  $sourceKind = "markdown"
}

$results = @()
foreach ($user in $parsedUsers) {
  $result = BuildUserResult $user
  if ($null -ne $result) { $results += $result }
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$baseName = [IO.Path]::GetFileNameWithoutExtension($resolvedInput)
$jsonPath = Join-Path $OutputDir "$baseName.diet_balance_kcal_results.json"
$csvPath = Join-Path $OutputDir "$baseName.diet_balance_kcal_summary.csv"

$payload = [pscustomobject][ordered]@{
  schema = "relty_diet_balance_calculator_kcal.v0_5"
  generated_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
  source_input = $resolvedInput
  source_kind = $sourceKind
  calculation_note = "Kcal variant calculator. Uses daily_total.food_group_totals or sums meal food_group_estimates when present; falls back to legacy food-name estimates only when structured food groups are missing. HEI-2020 now dynamically includes available moderation components from daily_total.moderation_estimates: saturated_fats, added_sugars, sodium, and fatty_acids. RDA/AI uses each user's user_profile when available: protein target is 0.8 g/kg/day from weight_kg, and fiber target uses age_years and sex. Diet Balance requires Kcal Balance, which is calculated only for complete-day records when a target kcal field or -DefaultTargetKcal is available. Incomplete records are marked incomplete_partial_day and are not ranked. Meal Timing is temporarily set to 100 until reliable multi-day timing data is available."
  defaults = [ordered]@{
    age_years = $DefaultAgeYears
    sex = $DefaultSex
    target_kcal = $DefaultTargetKcal
  }
  formula = "Diet Balance = 0.40*HEI_2020_available + 0.15*AMDR_Fit + 0.20*RDA_AI_Adequacy + 0.10*Meal_Timing + 0.15*Kcal_Balance"
  kcal_balance_formula = "Kcal_Balance = 100 when actual_kcal/target_kcal is 0.90-1.10; linearly decreases to 0 when deviation reaches 50% or more."
  users = $results
}

$payload | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$rows = foreach ($u in $results) {
  [pscustomobject]@{
    user_id = $u.user_id
    profile = $u.profile
    diet_balance = $u.diet_balance
    diet_balance_raw = $u.diet_balance_raw
    score_status = $u.score_status
    ranking_status = $u.ranking_status
    is_partial_day_score = $u.is_partial_day_score
    balance_method = $u.balance_method
    food_group_input_source = $u.debug.food_group_input_source
    kcal_target_source = $u.debug.kcal_target_source
    default_target_kcal = $u.default_target_kcal
    scoring_age_years = $u.scoring_profile.age_years
    scoring_sex = $u.scoring_profile.sex
    scoring_weight_kg = $u.scoring_profile.weight_kg
    hei_2020_available = $u.components.hei_2020_available
    hei_recognized_score_points = $u.debug.hei_2020_available.recognized_score_points
    hei_recognized_max_points = $u.debug.hei_2020_available.recognized_max_points
    hei_unscored_components = ($u.debug.hei_2020_available.unscored_components -join ";")
    amdr_fit = $u.components.amdr_fit
    rda_ai_adequacy = $u.components.rda_ai_adequacy
    meal_timing = $u.components.meal_timing
    kcal_balance = $u.components.kcal_balance
    structure = $u.abstract_scores.structure
    nutrients = $u.abstract_scores.nutrients
    rhythm = $u.abstract_scores.rhythm
    energy = $u.abstract_scores.energy
    hei_contribution = $u.contributions.hei_2020_available
    amdr_contribution = $u.contributions.amdr_fit
    rda_contribution = $u.contributions.rda_ai_adequacy
    meal_timing_contribution = $u.contributions.meal_timing
    kcal_contribution = $u.contributions.kcal_balance
    legacy_four_component_reference_raw = $u.legacy_four_component_reference_raw
    partial_without_kcal_reference_raw = $u.partial_without_kcal_reference_raw
  }
}
$rows | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding UTF8

[pscustomobject]@{
  json = $jsonPath
  csv = $csvPath
  users = $results.Count
  source_kind = $sourceKind
} | ConvertTo-Json
