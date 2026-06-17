param(
  [string]$ProjectRoot = (Get-Location).Path,
  [string]$DesignSystemDir = "design_system_paineis_indicadores"
)

$ErrorActionPreference = "Stop"
$failed = $false
$warnings = 0

function Write-Check {
  param([string]$Status, [string]$Message)
  Write-Host "[$Status] $Message"
}

$project = (Resolve-Path -LiteralPath $ProjectRoot).Path
$ds = Join-Path $project $DesignSystemDir

if (-not (Test-Path -LiteralPath $ds -PathType Container)) {
  Write-Check "FAIL" "Design system folder not found: $ds"
  Write-Host "Add it with:"
  Write-Host "git submodule add https://github.com/observatorio-fiesc/design_system_paineis_indicadores.git $DesignSystemDir"
  exit 1
}

Write-Check "OK" "Design system folder found: $DesignSystemDir"

$requiredDirs = @("tokens", "components", "templates", "raw-figma-css", "docs")
foreach ($dir in $requiredDirs) {
  $path = Join-Path $ds $dir
  if (Test-Path -LiteralPath $path -PathType Container) {
    Write-Check "OK" "$DesignSystemDir/$dir exists"
  } else {
    Write-Check "FAIL" "$DesignSystemDir/$dir is missing"
    $failed = $true
  }
}

$rg = Get-Command rg -ErrorAction SilentlyContinue
if (-not $rg) {
  Write-Check "WARN" "ripgrep (rg) not found; skipping source scans"
  exit ($(if ($failed) { 1 } else { 0 }))
}

$candidateDirs = @("src", "app", "pages", "components", "styles")
$scanRoots = @()
foreach ($candidate in $candidateDirs) {
  $candidatePath = Join-Path $project $candidate
  if (Test-Path -LiteralPath $candidatePath -PathType Container) {
    $scanRoots += $candidatePath
  }
}

if ($scanRoots.Count -eq 0) {
  Write-Check "WARN" "No app source directories found; checked only design-system structure"
  exit ($(if ($failed) { 1 } else { 0 }))
}

$commonGlobs = @(
  "--glob", "!**/$DesignSystemDir/**",
  "--glob", "!node_modules/**",
  "--glob", "!dist/**",
  "--glob", "!build/**",
  "--glob", "!.git/**",
  "--glob", "!.next/**",
  "--glob", "!coverage/**"
)

$rawMatches = & rg @commonGlobs "raw-figma-css" @scanRoots 2>$null
if ($LASTEXITCODE -eq 0) {
  Write-Check "FAIL" "Production code references raw-figma-css"
  $rawMatches | ForEach-Object { Write-Host $_ }
  $failed = $true
} else {
  Write-Check "OK" "No raw-figma-css references outside the design system folder"
}

$hexMatches = & rg @commonGlobs "#[0-9A-Fa-f]{6}\b" @scanRoots 2>$null
if ($LASTEXITCODE -eq 0) {
  Write-Check "WARN" "Hardcoded hex colors found; prefer --obs-* variables"
  $hexMatches | ForEach-Object { Write-Host $_ }
  $warnings++
} else {
  Write-Check "OK" "No hardcoded 6-digit hex colors found outside the design system folder"
}

$tokenMatches = & rg @commonGlobs "var\(--obs-" @scanRoots 2>$null
$classMatches = & rg @commonGlobs "obs-" @scanRoots 2>$null

if ($LASTEXITCODE -ne 0 -and -not $tokenMatches -and -not $classMatches) {
  Write-Check "WARN" "No --obs-* token or obs-* class usage detected in scanned files"
  $warnings++
} else {
  Write-Check "OK" "Detected design-system token or class usage"
}

if ($failed) {
  exit 1
}

if ($warnings -gt 0) {
  Write-Check "DONE" "Validation finished with $warnings warning(s)"
} else {
  Write-Check "DONE" "Validation finished without warnings"
}

exit 0
