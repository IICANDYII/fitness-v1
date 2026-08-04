param(
  [string]$InputPath,

  [string]$InputJson,

  [string]$InputMarkdown,

  [string]$OutputDir = ".\outputs",

  [int]$DefaultAgeYears = 30,

  [ValidateSet("female", "male")]
  [string]$DefaultSex = "female"
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

function BuildUserResult($user) {
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
  $dietBalance = ([double]$hei.hei_2020_available * 0.50) + ($amdrFit * 0.20) + ([double]$rda.rda_ai_adequacy_partial * 0.20) + ($mealTiming * 0.10)
  $structureScore = ((([double]$hei.hei_2020_available * 0.50) + ($amdrFit * 0.20)) / 0.70)

  return [pscustomobject][ordered]@{
    user_id = $user.user_id
    profile = $user.profile
    default_age_years = $DefaultAgeYears
    default_sex = $DefaultSex
    diet_balance = [Math]::Round($dietBalance, 0)
    diet_balance_raw = Round2 $dietBalance
    balance_method = "0.50*HEI_2020_available + 0.20*AMDR_Fit + 0.20*RDA_AI_Adequacy + 0.10*Meal_Timing"
    abstract_scores = [ordered]@{
      structure = Round2 $structureScore
      nutrients = $rda.rda_ai_adequacy_partial
      rhythm = Round2 $mealTiming
    }
    components = [ordered]@{
      hei_2020_available = $hei.hei_2020_available
      amdr_fit = Round2 $amdrFit
      rda_ai_adequacy = $rda.rda_ai_adequacy_partial
      meal_timing = Round2 $mealTiming
    }
    contributions = [ordered]@{
      hei_2020_available = Round2 ([double]$hei.hei_2020_available * 0.50)
      amdr_fit = Round2 ($amdrFit * 0.20)
      rda_ai_adequacy = Round2 ([double]$rda.rda_ai_adequacy_partial * 0.20)
      meal_timing = Round2 ($mealTiming * 0.10)
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
      coverage_flags = if (HasProperty $user.daily_total "coverage_flags") { $user.daily_total.coverage_flags } else { $null }
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
$jsonPath = Join-Path $OutputDir "$baseName.diet_balance_results.json"
$csvPath = Join-Path $OutputDir "$baseName.diet_balance_summary.csv"

$payload = [pscustomobject][ordered]@{
  schema = "relty_diet_balance_calculator.v0_2"
  generated_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
  source_input = $resolvedInput
  source_kind = $sourceKind
  calculation_note = "Updated for Diet Recognition Structured Output v2. Uses daily_total.food_group_totals or sums meal food_group_estimates when present; falls back to legacy food-name estimates only when structured food groups are missing. The current calculation standard follows the calculator formula: Diet Balance = 0.50*HEI_2020_available + 0.20*AMDR_Fit + 0.20*RDA_AI_Adequacy + 0.10*Meal_Timing. Meal Timing is temporarily set to 100 until reliable multi-day timing data is available."
  defaults = [ordered]@{
    age_years = $DefaultAgeYears
    sex = $DefaultSex
  }
  formula = "Diet Balance = 0.50*HEI_2020_available + 0.20*AMDR_Fit + 0.20*RDA_AI_Adequacy + 0.10*Meal_Timing"
  users = $results
}

$payload | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$rows = foreach ($u in $results) {
  [pscustomobject]@{
    user_id = $u.user_id
    profile = $u.profile
    diet_balance = $u.diet_balance
    diet_balance_raw = $u.diet_balance_raw
    balance_method = $u.balance_method
    food_group_input_source = $u.debug.food_group_input_source
    hei_2020_available = $u.components.hei_2020_available
    amdr_fit = $u.components.amdr_fit
    rda_ai_adequacy = $u.components.rda_ai_adequacy
    meal_timing = $u.components.meal_timing
    structure = $u.abstract_scores.structure
    nutrients = $u.abstract_scores.nutrients
    rhythm = $u.abstract_scores.rhythm
    hei_contribution = $u.contributions.hei_2020_available
    amdr_contribution = $u.contributions.amdr_fit
    rda_contribution = $u.contributions.rda_ai_adequacy
    meal_timing_contribution = $u.contributions.meal_timing
  }
}
$rows | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding UTF8

[pscustomobject]@{
  json = $jsonPath
  csv = $csvPath
  users = $results.Count
  source_kind = $sourceKind
} | ConvertTo-Json
