param(
  [string]$InputPath,

  [string]$InputJson,

  [string]$InputMarkdown,

  [string]$OutputDir = ".\outputs",

  [int]$DefaultAgeYears = 30,

  [ValidateSet("female", "male")]
  [string]$DefaultSex = "female",

  [Nullable[double]]$DefaultTargetKcal = $null,

  [int]$BaselineMinLearningDays = 7,

  [double]$BaselineMinDeltaPoints = 1.0,

  [double]$BaselineRawMappedMaxPoints = 30.0
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

function AddHeiComponentIfIncluded([object[]]$components, $include, [string]$key, $component) {
  if ($include.$key) { return @($components + $component) }
  return $components
}

function CalculateHeiAvailable($groups, [double]$kcal, $include) {
  if ($kcal -le 0) { throw "kcal_mid must be greater than zero for HEI density scoring." }
  $per1000 = $kcal / 1000.0
  $components = @()

  # Diet Recognition v2 intentionally omits sodium, saturated fat, added sugars,
  # and fatty acid quality; score only the structured HEI components available.
  $components = AddHeiComponentIfIncluded $components $include "total_fruits" (HeiAdequacyComponent "total_fruits" ($groups.total_fruits_cup / $per1000) 0.8 5.0)
  $components = AddHeiComponentIfIncluded $components $include "whole_fruits" (HeiAdequacyComponent "whole_fruits" ($groups.whole_fruits_cup / $per1000) 0.4 5.0)
  $components = AddHeiComponentIfIncluded $components $include "total_vegetables" (HeiAdequacyComponent "total_vegetables" ($groups.total_vegetables_cup / $per1000) 1.1 5.0)
  $components = AddHeiComponentIfIncluded $components $include "greens_and_beans" (HeiAdequacyComponent "greens_and_beans" ($groups.greens_and_beans_cup / $per1000) 0.2 5.0)
  $components = AddHeiComponentIfIncluded $components $include "whole_grains" (HeiAdequacyComponent "whole_grains" ($groups.whole_grains_oz / $per1000) 1.5 10.0)
  $components = AddHeiComponentIfIncluded $components $include "dairy" (HeiAdequacyComponent "dairy" ($groups.dairy_cup / $per1000) 1.3 10.0)
  $components = AddHeiComponentIfIncluded $components $include "total_protein_foods" (HeiAdequacyComponent "total_protein_foods" ($groups.total_protein_foods_oz / $per1000) 2.5 5.0)
  $components = AddHeiComponentIfIncluded $components $include "seafood_and_plant_proteins" (HeiAdequacyComponent "seafood_and_plant_proteins" ($groups.seafood_and_plant_proteins_oz / $per1000) 0.8 5.0)
  $components = AddHeiComponentIfIncluded $components $include "refined_grains" (HeiModerationComponent "refined_grains" ($groups.refined_grains_oz / $per1000) 1.8 4.3 10.0)

  $score = 0.0
  $max = 0.0
  foreach ($component in $components) {
    $score += [double]$component.score
    $max += [double]$component.max_points
  }

  return [pscustomobject]@{
    hei_2020_available = if ($max -gt 0) { Round2 (($score / $max) * 100.0) } else { 0.0 }
    recognized_score_points = Round2 $score
    recognized_max_points = Round2 $max
    components = $components
    unscored_components = @(
      "fatty_acids",
      "sodium",
      "added_sugars",
      "saturated_fats"
    )
    food_group_totals_used = $groups
    included_components = $include
  }
}

function CalculateRdaExplanation([double]$proteinG, [double]$fiberG, [int]$age, [string]$sex) {
  if ([string]::IsNullOrWhiteSpace($sex)) { $sex = "female" }
  if ($age -le 0) { $age = 30 }

  $proteinTarget = if ($sex -eq "male") { 56.0 } else { 46.0 }
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
    note = "Protein is derived from kcal_mid and macro protein percentage. Fiber is read from Diet Recognition v2 structured fields when available, otherwise estimated by the legacy fallback."
    rda_ai_adequacy_partial = Round2 $rdaAiAdequacy
    recognized_weight_sum = 0.40
    protein = [pscustomobject]@{
      actual_g = Round2 $proteinG
      target_g = $proteinTarget
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

function ClampDouble([double]$value, [double]$min, [double]$max) {
  if ($value -lt $min) { return $min }
  if ($value -gt $max) { return $max }
  return $value
}

function MedianDouble([double[]]$values) {
  $clean = @($values | Where-Object { $null -ne $_ } | Sort-Object)
  if ($clean.Count -eq 0) { return $null }
  $middle = [int][Math]::Floor($clean.Count / 2)
  if (($clean.Count % 2) -eq 1) { return [double]$clean[$middle] }
  return ([double]$clean[$middle - 1] + [double]$clean[$middle]) / 2.0
}

function NormalizeScore100([Nullable[double]]$score, [double]$maxPoints = 100.0) {
  if ($null -eq $score) { return $null }
  if ($maxPoints -le 0) { return $null }
  return ClampDouble (([double]$score / $maxPoints) * 100.0) 0.0 100.0
}

function Get-BaselineComponentWeights() {
  # Same component family as Reference Balance, scaled to a 10-point baseline term.
  # Reference formula: 0.40 HEI + 0.15 AMDR + 0.20 RDA/AI + 0.10 Meal Timing + 0.15 Kcal Balance.
  return [ordered]@{
    hei_2020_available = 4.0
    amdr_fit = 1.5
    rda_ai_adequacy = 2.0
    meal_timing = 1.0
    kcal_balance = 1.5
  }
}

function Get-ImprovementLevel([double]$delta) {
  if ($delta -lt $BaselineMinDeltaPoints) { return "none" }
  if ($delta -lt 3.0) { return "mild" }
  if ($delta -lt 5.0) { return "moderate" }
  return "strong"
}

function Get-ImprovementFactor([string]$level) {
  switch ($level) {
    "mild" { return 0.4 }
    "moderate" { return 0.7 }
    "strong" { return 1.0 }
    default { return 0.0 }
  }
}

function Get-ComponentScoreValue($object, [string]$name) {
  if ($null -eq $object) { return $null }
  if (HasProperty $object $name -and $null -ne $object.$name) { return [double]$object.$name }
  return $null
}

function Get-ComponentScores100FromBreakdown($breakdown) {
  return [ordered]@{
    hei_2020_available = NormalizeScore100 ([double]$breakdown.hei.hei_2020_available) 100.0
    amdr_fit = NormalizeScore100 ([double]$breakdown.amdr_fit) 100.0
    rda_ai_adequacy = NormalizeScore100 ([double]$breakdown.rda.rda_ai_adequacy_partial) 100.0
    meal_timing = NormalizeScore100 ([double]$breakdown.meal_timing) 100.0
    kcal_balance = if ($null -ne $breakdown.kcal_balance) { NormalizeScore100 ([double]$breakdown.kcal_balance.score) 100.0 } else { $null }
  }
}

function Get-ComponentScores100FromStoredObject($object) {
  if ($null -eq $object) { return $null }

  $containers = @()
  foreach ($field in @(
    "component_scores_100",
    "component_score_100",
    "reference_component_scores_100",
    "baseline_component_scores_100",
    "components_100"
  )) {
    if (HasProperty $object $field -and $null -ne $object.$field) {
      $containers += $object.$field
    }
  }
  $containers += $object

  foreach ($container in $containers) {
    $scores = [ordered]@{}
    foreach ($componentName in @((Get-BaselineComponentWeights).Keys)) {
      $value = Get-ComponentScoreValue $container $componentName
      if ($null -ne $value) { $scores[$componentName] = ClampDouble $value 0.0 100.0 }
    }
    if ($scores.Count -gt 0) { return [pscustomobject]$scores }
  }

  return $null
}

function Get-ProvidedBaselineMedians($user) {
  $containers = @()
  foreach ($name in @("baseline", "diet_baseline", "personal_baseline")) {
    if (HasProperty $user $name -and $null -ne $user.$name) { $containers += $user.$name }
  }
  $containers += $user

  foreach ($container in $containers) {
    foreach ($field in @("component_score_medians_100", "component_medians_100", "baseline_component_medians_100", "component_scores_100")) {
      if (HasProperty $container $field -and $null -ne $container.$field) {
        $src = $container.$field
        $medians = [ordered]@{}
        foreach ($componentName in @((Get-BaselineComponentWeights).Keys)) {
          $value = Get-ComponentScoreValue $src $componentName
          if ($null -ne $value) { $medians[$componentName] = ClampDouble $value 0.0 100.0 }
        }
        if ($medians.Count -gt 0) {
          $learningDays = if (HasProperty $container "learning_period_days") { [int]$container.learning_period_days } else { $null }
          if ($null -ne $learningDays -and $learningDays -lt $BaselineMinLearningDays) {
            return [pscustomobject][ordered]@{
              available = $false
              source = "$field.learning_period_days_insufficient"
              medians = $null
              learning_period_days = $learningDays
              note = "Need at least $BaselineMinLearningDays learning days before enabling provided baseline medians."
            }
          }
          return [pscustomobject][ordered]@{
            available = $true
            source = $field
            medians = [pscustomobject]$medians
            learning_period_days = $learningDays
          }
        }
      }
    }
  }

  return [pscustomobject][ordered]@{
    available = $false
    source = "not_provided"
    medians = $null
    learning_period_days = $null
  }
}

function Get-BaselineRecords($user) {
  foreach ($field in @("baseline_days", "baseline_records", "learning_period_records", "diet_baseline_days")) {
    if (HasProperty $user $field -and $null -ne $user.$field) {
      return @($user.$field)
    }
  }
  if (HasProperty $user "baseline" -and $null -ne $user.baseline) {
    foreach ($field in @("days", "records", "baseline_days", "learning_period_records")) {
      if (HasProperty $user.baseline $field -and $null -ne $user.baseline.$field) {
        return @($user.baseline.$field)
      }
    }
  }
  return @()
}

function CalculateReferenceBreakdown($user) {
  if ($null -eq $user.daily_total) { return $null }

  $kcalMid = [double]$user.daily_total.kcal_mid
  $carbPct = [double]$user.daily_total.macro_structure_pct.carb / 100.0
  $fatPct = [double]$user.daily_total.macro_structure_pct.fat / 100.0
  $proteinPct = [double]$user.daily_total.macro_structure_pct.protein / 100.0
  $proteinG = ($kcalMid * $proteinPct) / 4.0

  $groups = Convert-V2FoodGroupTotals $user
  if (-not $groups.structured_food_groups_available) {
    $groups = EstimateFoodGroupsFromNames $user.meals
  }

  $heiInclusion = Get-HeiComponentInclusion $user $groups
  $hei = CalculateHeiAvailable $groups $kcalMid $heiInclusion
  $carbScore = MacroRangeScore $carbPct 0.45 0.65 0.25 0.80
  $fatScore = MacroRangeScore $fatPct 0.20 0.35 0.10 0.50
  $proteinMacroScore = MacroRangeScore $proteinPct 0.10 0.35 0.05 0.45
  $amdrFit = ($carbScore * 0.40) + ($fatScore * 0.30) + ($proteinMacroScore * 0.30)
  $rda = CalculateRdaExplanation $proteinG ([double]$groups.fiber_g) $DefaultAgeYears $DefaultSex
  $mealTiming = 100.0
  $kcalTarget = Get-KcalTarget $user
  $kcalBalance = if ($kcalTarget.available) { KcalBalanceScore $kcalMid ([double]$kcalTarget.value) } else { $null }
  $referenceBalance = if ($null -ne $kcalBalance) {
    ([double]$hei.hei_2020_available * 0.40) + ($amdrFit * 0.15) + ([double]$rda.rda_ai_adequacy_partial * 0.20) + ($mealTiming * 0.10) + ([double]$kcalBalance.score * 0.15)
  }
  else {
    $null
  }
  $legacyReferenceBalance = ([double]$hei.hei_2020_available * 0.50) + ($amdrFit * 0.20) + ([double]$rda.rda_ai_adequacy_partial * 0.20) + ($mealTiming * 0.10)
  $structureScore = ((([double]$hei.hei_2020_available * 0.40) + ($amdrFit * 0.15)) / 0.55)

  $breakdown = [pscustomobject][ordered]@{
    kcal_mid = $kcalMid
    carb_pct = $carbPct
    fat_pct = $fatPct
    protein_pct = $proteinPct
    protein_g = $proteinG
    groups = $groups
    hei_inclusion = $heiInclusion
    hei = $hei
    carb_score = $carbScore
    fat_score = $fatScore
    protein_macro_score = $proteinMacroScore
    amdr_fit = $amdrFit
    rda = $rda
    meal_timing = $mealTiming
    kcal_target = $kcalTarget
    kcal_balance = $kcalBalance
    reference_balance_raw = $referenceBalance
    legacy_four_component_reference_raw = $legacyReferenceBalance
    structure_score = $structureScore
  }
  $breakdown | Add-Member -NotePropertyName component_scores_100 -NotePropertyValue (Get-ComponentScores100FromBreakdown $breakdown)
  return $breakdown
}

function Build-BaselineMediansFromRecords($records) {
  if ($records.Count -lt $BaselineMinLearningDays) {
    return [pscustomobject][ordered]@{
      available = $false
      source = "baseline_records_insufficient"
      medians = $null
      learning_period_days = $records.Count
      note = "Need at least $BaselineMinLearningDays baseline records before enabling baseline score."
    }
  }

  $collector = [ordered]@{}
  foreach ($componentName in @((Get-BaselineComponentWeights).Keys)) { $collector[$componentName] = @() }

  $storedScoreRecordCount = 0
  $computedScoreRecordCount = 0

  foreach ($record in $records) {
    $componentScores = Get-ComponentScores100FromStoredObject $record
    if ($null -ne $componentScores) {
      $storedScoreRecordCount += 1
    }
    else {
      $breakdown = CalculateReferenceBreakdown $record
      if ($null -eq $breakdown) { continue }
      $componentScores = [pscustomobject]$breakdown.component_scores_100
      $computedScoreRecordCount += 1
    }

    foreach ($componentName in @((Get-BaselineComponentWeights).Keys)) {
      $value = Get-ComponentScoreValue $componentScores $componentName
      if ($null -ne $value) { $collector[$componentName] += [double]$value }
    }
  }

  $medians = [ordered]@{}
  foreach ($componentName in @((Get-BaselineComponentWeights).Keys)) {
    $median = MedianDouble ([double[]]$collector[$componentName])
    if ($null -ne $median) { $medians[$componentName] = Round2 $median }
  }

  if ($medians.Count -eq 0) {
    return [pscustomobject][ordered]@{
      available = $false
      source = "baseline_records_no_scored_components"
      medians = $null
      learning_period_days = $records.Count
      note = "Baseline records exist, but no scorable component medians could be calculated."
    }
  }

  $source = if ($storedScoreRecordCount -gt 0 -and $computedScoreRecordCount -eq 0) {
    "stored_baseline_record_component_scores_median_7d"
  }
  elseif ($storedScoreRecordCount -gt 0 -and $computedScoreRecordCount -gt 0) {
    "mixed_stored_and_computed_baseline_record_component_scores_median_7d"
  }
  else {
    "computed_from_baseline_records_median_7d"
  }

  $note = if ($storedScoreRecordCount -gt 0 -and $computedScoreRecordCount -eq 0) {
    "Baseline component medians are calculated from component scores already stored on the user's baseline records."
  }
  elseif ($storedScoreRecordCount -gt 0 -and $computedScoreRecordCount -gt 0) {
    "Baseline component medians are calculated from stored component scores when available, with missing record scores computed using the same reference component scoring functions."
  }
  else {
    "Baseline component medians are calculated from the user's baseline records using the same reference component scoring functions."
  }

  return [pscustomobject][ordered]@{
    available = $true
    source = $source
    medians = [pscustomobject]$medians
    learning_period_days = $records.Count
    stored_score_record_count = $storedScoreRecordCount
    computed_score_record_count = $computedScoreRecordCount
    note = $note
  }
}

function Resolve-BaselineMedians($user) {
  $provided = Get-ProvidedBaselineMedians $user
  if ($provided.available) { return $provided }

  $records = Get-BaselineRecords $user
  if ($records.Count -gt 0) { return Build-BaselineMediansFromRecords $records }

  return [pscustomobject][ordered]@{
    available = $false
    source = "not_available"
    medians = $null
    learning_period_days = 0
    note = "No baseline medians or baseline records were provided; baseline score is disabled and contributes 0."
  }
}

function CalculateBaselineScore($user, $todayComponentScores100) {
  $weights = Get-BaselineComponentWeights
  $baseline = Resolve-BaselineMedians $user

  if (-not $baseline.available) {
    return [pscustomobject][ordered]@{
      available = $false
      status = "not_available"
      source = $baseline.source
      baseline_score = 0.0
      baseline_score_raw = 0.0
      baseline_score_raw_scale_max = 0.0
      baseline_score_raw_mapped = 0.0
      baseline_score_raw_mapped_cap = $BaselineRawMappedMaxPoints
      baseline_score_threshold_capped = 0.0
      score_cap = 10.0
      component_medians_100 = $null
      components = @()
      thresholds = [ordered]@{
        minimum_meaningful_delta_points = $BaselineMinDeltaPoints
        mild = "delta >= $BaselineMinDeltaPoints and < 3"
        moderate = "delta >= 3 and < 5"
        strong = "delta >= 5"
      }
      note = $baseline.note
    }
  }

  $components = @()
  $appliedTotal = 0.0
  $rawTotal = 0.0
  $rawScaleMaxTotal = 0.0

  foreach ($componentName in @($weights.Keys)) {
    $today = $todayComponentScores100[$componentName]
    $median = Get-ComponentScoreValue $baseline.medians $componentName
    if ($null -eq $today -or $null -eq $median) { continue }

    $delta = [double]$today - [double]$median
    $level = Get-ImprovementLevel $delta
    $factor = Get-ImprovementFactor $level
    $maxPoints = [double]$weights[$componentName]
    $appliedPoints = [Math]::Min($maxPoints, $maxPoints * $factor)

    # Raw score keeps the overflow signal before normalization. A delta of 5
    # points on the 100-point component scale earns 1x raw credit; a delta of
    # 10 earns 2x raw credit.
    $rawFactor = if ($delta -lt $BaselineMinDeltaPoints) { 0.0 } else { [Math]::Max($factor, $delta / 5.0) }
    $rawPoints = $maxPoints * $rawFactor
    $maxDelta = [Math]::Max(0.0, 100.0 - [double]$median)
    $maxLevel = Get-ImprovementLevel $maxDelta
    $maxFactor = Get-ImprovementFactor $maxLevel
    $rawScaleMaxFactor = if ($maxDelta -lt $BaselineMinDeltaPoints) { 0.0 } else { [Math]::Max($maxFactor, $maxDelta / 5.0) }
    $rawScaleMaxPoints = $maxPoints * $rawScaleMaxFactor

    $appliedTotal += $appliedPoints
    $rawTotal += $rawPoints
    $rawScaleMaxTotal += $rawScaleMaxPoints

    $components += [pscustomobject][ordered]@{
      component = $componentName
      max_baseline_points = Round2 $maxPoints
      today_score_100 = Round2 $today
      baseline_median_100 = Round2 $median
      delta_points = Round2 $delta
      improvement_level = $level
      applied_points = Round2 $appliedPoints
      raw_points = Round2 $rawPoints
      raw_scale_max_points = Round2 $rawScaleMaxPoints
      scoring_note = "Compare normalized 0-100 component score against the 7-day baseline median. raw_points preserve overflow before normalization; raw_scale_max_points is the component's theoretical raw maximum from its stored baseline median to 100."
    }
  }

  $baselineScoreRawMapped = if ($rawScaleMaxTotal -gt 0) {
    [Math]::Min($BaselineRawMappedMaxPoints, ($rawTotal / $rawScaleMaxTotal) * $BaselineRawMappedMaxPoints)
  }
  else {
    0.0
  }
  $baselineScore = [Math]::Min(10.0, $baselineScoreRawMapped)

  return [pscustomobject][ordered]@{
    available = $true
    status = "available"
    source = $baseline.source
    learning_period_days = $baseline.learning_period_days
    baseline_score = Round2 $baselineScore
    baseline_score_raw = Round2 $rawTotal
    baseline_score_raw_scale_max = Round2 $rawScaleMaxTotal
    baseline_score_raw_mapped = Round2 $baselineScoreRawMapped
    baseline_score_raw_mapped_cap = Round2 $BaselineRawMappedMaxPoints
    baseline_score_threshold_capped = Round2 ([Math]::Min(10.0, $appliedTotal))
    score_cap = 10.0
    component_medians_100 = $baseline.medians
    components = $components
    thresholds = [ordered]@{
      minimum_meaningful_delta_points = $BaselineMinDeltaPoints
      mild = "delta >= $BaselineMinDeltaPoints and < 3"
      moderate = "delta >= 3 and < 5"
      strong = "delta >= 5"
    }
    note = "Baseline Score reuses the same Diet Balance component scores. It compares today against the user's 7-day median baseline, preserves raw overflow, maps raw overflow back to a 0-$BaselineRawMappedMaxPoints scale, then caps the final display contribution at 10."
  }
}

function BuildUserResult($user) {
  $breakdown = CalculateReferenceBreakdown $user
  if ($null -eq $breakdown) { return $null }

  $referenceBalance = $breakdown.reference_balance_raw
  $baseline = CalculateBaselineScore $user $breakdown.component_scores_100
  $displayBalance = if ($null -ne $referenceBalance) { [Math]::Min(100.0, [double]$referenceBalance + [double]$baseline.baseline_score) } else { $null }

  return [pscustomobject][ordered]@{
    user_id = $user.user_id
    profile = $user.profile
    default_age_years = $DefaultAgeYears
    default_sex = $DefaultSex
    default_target_kcal = $DefaultTargetKcal
    diet_balance = if ($null -ne $displayBalance) { [Math]::Round($displayBalance, 0) } else { $null }
    diet_balance_raw = Round2 $displayBalance
    reference_balance = if ($null -ne $referenceBalance) { [Math]::Round($referenceBalance, 0) } else { $null }
    reference_balance_raw = Round2 $referenceBalance
    baseline_score = $baseline.baseline_score
    baseline_score_raw = $baseline.baseline_score_raw
    baseline_score_raw_scale_max = $baseline.baseline_score_raw_scale_max
    baseline_score_raw_mapped = $baseline.baseline_score_raw_mapped
    baseline_score_raw_mapped_cap = $baseline.baseline_score_raw_mapped_cap
    baseline_score_threshold_capped = $baseline.baseline_score_threshold_capped
    score_status = if ($null -ne $displayBalance) { "complete_with_kcal_balance" } else { "kcal_target_unavailable" }
    balance_method = "Display Diet Balance = min(Reference_Balance + Baseline_Score, 100). Reference_Balance = 0.40*HEI_2020_available + 0.15*AMDR_Fit + 0.20*RDA_AI_Adequacy + 0.10*Meal_Timing + 0.15*Kcal_Balance. Baseline raw overflow is normalized to a 0-$BaselineRawMappedMaxPoints scale, then Baseline_Score is capped at 10."
    legacy_four_component_reference_raw = Round2 $breakdown.legacy_four_component_reference_raw
    abstract_scores = [ordered]@{
      structure = Round2 $breakdown.structure_score
      nutrients = $breakdown.rda.rda_ai_adequacy_partial
      rhythm = Round2 $breakdown.meal_timing
      energy = if ($null -ne $breakdown.kcal_balance) { $breakdown.kcal_balance.score } else { $null }
    }
    components = [ordered]@{
      hei_2020_available = $breakdown.hei.hei_2020_available
      amdr_fit = Round2 $breakdown.amdr_fit
      rda_ai_adequacy = $breakdown.rda.rda_ai_adequacy_partial
      meal_timing = Round2 $breakdown.meal_timing
      kcal_balance = if ($null -ne $breakdown.kcal_balance) { $breakdown.kcal_balance.score } else { $null }
    }
    component_scores_100 = $breakdown.component_scores_100
    contributions = [ordered]@{
      reference_hei_2020_available = Round2 ([double]$breakdown.hei.hei_2020_available * 0.40)
      reference_amdr_fit = Round2 ($breakdown.amdr_fit * 0.15)
      reference_rda_ai_adequacy = Round2 ([double]$breakdown.rda.rda_ai_adequacy_partial * 0.20)
      reference_meal_timing = Round2 ($breakdown.meal_timing * 0.10)
      reference_kcal_balance = if ($null -ne $breakdown.kcal_balance) { Round2 ([double]$breakdown.kcal_balance.score * 0.15) } else { $null }
      baseline_score = $baseline.baseline_score
    }
    baseline = $baseline
    debug = [ordered]@{
      amdr = [ordered]@{
        included_in_diet_balance = $true
        carb_pct = Round4 $breakdown.carb_pct
        fat_pct = Round4 $breakdown.fat_pct
        protein_pct = Round4 $breakdown.protein_pct
        carb_score = Round2 $breakdown.carb_score
        fat_score = Round2 $breakdown.fat_score
        protein_score = Round2 $breakdown.protein_macro_score
      }
      hei_2020_available = $breakdown.hei
      rda_ai_partial = $breakdown.rda
      kcal_balance = if ($null -ne $breakdown.kcal_balance) { $breakdown.kcal_balance } else {
        [ordered]@{
          included_in_diet_balance = $false
          score = $null
          target_kcal = $null
          target_source = $breakdown.kcal_target.source
          note = "Kcal Balance requires target_kcal, tdee_kcal, estimated_energy_requirement_kcal, energy_requirement_kcal, energy_need_kcal, recommended_kcal, or -DefaultTargetKcal."
        }
      }
      kcal_target_source = $breakdown.kcal_target.source
      coverage_flags = if (HasProperty $user.daily_total "coverage_flags") { $user.daily_total.coverage_flags } else { $null }
      food_group_input_source = $breakdown.groups.input_source
      meal_timing_policy = "temporary_full_score_until_reliable_multi_day_timing_data"
      baseline_policy = "Baseline compares normalized component scores, not raw nutrition amounts. It prefers stored baseline component scores/medians; when missing, it computes component scores from baseline records. Raw overflow is mapped back to a 0-$BaselineRawMappedMaxPoints scale and final Baseline_Score is capped at 10."
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
  schema = "relty_diet_balance_calculator_kcal.v0_4_baseline_score"
  generated_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
  source_input = $resolvedInput
  source_kind = $sourceKind
  calculation_note = "Kcal variant calculator with Personal Baseline Score. Uses daily_total.food_group_totals or sums meal food_group_estimates when present; falls back to legacy food-name estimates only when structured food groups are missing. Reference Balance requires Kcal Balance, which is calculated only when a target kcal field or -DefaultTargetKcal is available. Meal Timing is temporarily set to 100 until reliable multi-day timing data is available. Baseline Score contributes 0-10 only when baseline medians or at least 7 baseline records are provided; stored baseline component scores are preferred and raw overflow is normalized to a 0-$BaselineRawMappedMaxPoints scale."
  defaults = [ordered]@{
    age_years = $DefaultAgeYears
    sex = $DefaultSex
    target_kcal = $DefaultTargetKcal
    baseline_min_learning_days = $BaselineMinLearningDays
    baseline_min_delta_points = $BaselineMinDeltaPoints
    baseline_raw_mapped_max_points = $BaselineRawMappedMaxPoints
  }
  formula = "Display_Diet_Balance = min(Reference_Balance + Baseline_Score, 100). Reference_Balance = 0.40*HEI_2020_available + 0.15*AMDR_Fit + 0.20*RDA_AI_Adequacy + 0.10*Meal_Timing + 0.15*Kcal_Balance. Baseline_Score = min(Baseline_Raw_Mapped_0_$BaselineRawMappedMaxPoints, 10)."
  reference_balance_formula = "Reference_Balance = 0.40*HEI_2020_available + 0.15*AMDR_Fit + 0.20*RDA_AI_Adequacy + 0.10*Meal_Timing + 0.15*Kcal_Balance"
  baseline_score_formula = "For each component, delta = today_component_score_100 - baseline_median_component_score_100. Stored baseline medians or stored per-record component scores are preferred; missing component scores are computed from baseline records. Raw points = component_weight * max(level_factor, delta/5), with no credit below the minimum meaningful delta. Raw max is computed from each component median to 100, raw total is mapped to 0-$BaselineRawMappedMaxPoints, and final Baseline_Score is capped at 10."
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
    reference_balance = $u.reference_balance
    reference_balance_raw = $u.reference_balance_raw
    baseline_score = $u.baseline_score
    baseline_score_raw = $u.baseline_score_raw
    baseline_score_raw_scale_max = $u.baseline_score_raw_scale_max
    baseline_score_raw_mapped = $u.baseline_score_raw_mapped
    baseline_score_raw_mapped_cap = $u.baseline_score_raw_mapped_cap
    baseline_score_threshold_capped = $u.baseline_score_threshold_capped
    baseline_status = $u.baseline.status
    baseline_source = $u.baseline.source
    score_status = $u.score_status
    balance_method = $u.balance_method
    food_group_input_source = $u.debug.food_group_input_source
    kcal_target_source = $u.debug.kcal_target_source
    default_target_kcal = $u.default_target_kcal
    hei_2020_available = $u.components.hei_2020_available
    amdr_fit = $u.components.amdr_fit
    rda_ai_adequacy = $u.components.rda_ai_adequacy
    meal_timing = $u.components.meal_timing
    kcal_balance = $u.components.kcal_balance
    structure = $u.abstract_scores.structure
    nutrients = $u.abstract_scores.nutrients
    rhythm = $u.abstract_scores.rhythm
    energy = $u.abstract_scores.energy
    reference_hei_contribution = $u.contributions.reference_hei_2020_available
    reference_amdr_contribution = $u.contributions.reference_amdr_fit
    reference_rda_contribution = $u.contributions.reference_rda_ai_adequacy
    reference_meal_timing_contribution = $u.contributions.reference_meal_timing
    reference_kcal_contribution = $u.contributions.reference_kcal_balance
    baseline_contribution = $u.contributions.baseline_score
    legacy_four_component_reference_raw = $u.legacy_four_component_reference_raw
  }
}
$rows | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding UTF8

[pscustomobject]@{
  json = $jsonPath
  csv = $csvPath
  users = $results.Count
  source_kind = $sourceKind
} | ConvertTo-Json
