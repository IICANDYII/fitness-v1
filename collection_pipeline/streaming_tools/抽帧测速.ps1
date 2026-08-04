$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = 'F drive streaming frame extraction benchmark'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$python = 'C:\Users\maxga\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$script = 'C:\Users\maxga\Documents\Codex\2026-08-04\na-s\outputs\stream_extract_sd.py'
$source = 'F:\VIDEO'
$outputRoot = 'E:\_pipeline_scratch\sd_direct_benchmark'

Write-Host 'F: streaming extraction benchmark' -ForegroundColor Cyan
Write-Host 'Input remains read-only. Frames are written directly into one ZIP.' -ForegroundColor DarkGray
Write-Host ''

& $python $script --source $source --output-root $outputRoot --fps 2 --max-edge 1280
$exitCode = $LASTEXITCODE

Write-Host ''
if ($exitCode -eq 0) {
    Write-Host 'Benchmark completed successfully.' -ForegroundColor Green
} else {
    Write-Host "Benchmark ended with exit code $exitCode. See the summary above." -ForegroundColor Yellow
}
Read-Host 'Press Enter to close this window'
exit $exitCode
