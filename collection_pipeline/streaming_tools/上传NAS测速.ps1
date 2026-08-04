$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = 'NAS upload benchmark'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$python = 'C:\Users\maxga\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$script = 'C:\Users\maxga\Documents\Codex\2026-08-04\na-s\outputs\upload_frames_to_nas.py'

& $python $script
$exitCode = $LASTEXITCODE

Write-Host ''
if ($exitCode -eq 0) {
    Write-Host 'Upload benchmark completed successfully.' -ForegroundColor Green
} else {
    Write-Host "Upload benchmark ended with exit code $exitCode." -ForegroundColor Yellow
}
Read-Host 'Press Enter to close this window'
exit $exitCode
