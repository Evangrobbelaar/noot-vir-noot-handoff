# ============================================================================
#  Noot-vir-Noot gameshow - one-command installer for a fresh Windows laptop
# ============================================================================
#  Run in PowerShell (no coding tools needed on the laptop):
#
#    irm https://raw.githubusercontent.com/Evangrobbelaar/noot-vir-noot-handoff/gameshow-final/install_gameshow.ps1 | iex
#
#  Installs: Python 3.12, VLC (64-bit), the gameshow software and its Python
#  packages, into %USERPROFILE%\Gameshow, plus desktop shortcuts.
#  The show VIDEOS are NOT installed: copy them into %USERPROFILE%\Gameshow\vid
#  (vrae\, countdown\, visual\) from the video zip.
#  Running it again UPDATES the software and keeps the videos and scores.
# ============================================================================

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"            # much faster downloads in PowerShell 5
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repo     = "Evangrobbelaar/noot-vir-noot-handoff"
$Branch   = if ($env:GAMESHOW_BRANCH) { $env:GAMESHOW_BRANCH } else { "gameshow-final" }
$AppDir   = "10_FINAL_CURRENT_2026-04-to-present"
$Dest     = if ($env:GAMESHOW_DIR) { $env:GAMESHOW_DIR } else { Join-Path $env:USERPROFILE "Gameshow" }
$Python   = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"

function Step($n, $msg) { Write-Host "`n[$n/7] $msg" -ForegroundColor Cyan }
function Ok($msg)       { Write-Host "      $msg" -ForegroundColor Green }
function Fail($msg)     { Write-Host "`nFOUT: $msg" -ForegroundColor Red; if (-not $env:GAMESHOW_NOPAUSE) { Read-Host "Druk Enter om toe te maak" }; exit 1 }

Write-Host "Noot-vir-Noot gameshow installer" -ForegroundColor Yellow
Write-Host "Installeer na: $Dest"

# 1. winget (Windows' own app installer, built into Windows 10/11)
Step 1 "Kontroleer Windows App Installer (winget)"
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Fail "winget ontbreek. Installeer 'App Installer' uit die Microsoft Store en probeer weer."
}
Ok "winget gevind"

# 2. Python 3.12 (64-bit, for this user only - no admin needed)
Step 2 "Python 3.12"
if (-not (Test-Path $Python)) {
    winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements | Out-Host
    if (-not (Test-Path $Python)) { Fail "Python kon nie installeer nie." }
}
Ok (& $Python --version)

# 3. VLC media player, 64-bit (plays the videos; Windows may ask permission)
Step 3 "VLC media player (64-bit)"
$vlcDll = Join-Path $env:ProgramFiles "VideoLAN\VLC\libvlc.dll"
if (-not (Test-Path $vlcDll)) {
    winget install -e --id VideoLAN.VLC --architecture x64 --silent --accept-package-agreements --accept-source-agreements | Out-Host
    if (-not (Test-Path $vlcDll)) { Fail "VLC kon nie installeer nie. Installeer VLC 64-bit van videolan.org en probeer weer." }
}
Ok "VLC gevind"

# 4. The gameshow software (downloaded from GitHub; no git needed)
Step 4 "Laai die gameshow sagteware af"
$tmp = Join-Path $env:TEMP ("gameshow_install_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force $tmp | Out-Null
$zip = Join-Path $tmp "code.zip"
try {
    Invoke-WebRequest "https://github.com/$Repo/archive/refs/heads/$Branch.zip" -OutFile $zip -UseBasicParsing
} catch { Fail "Kon nie van GitHub aflaai nie. Is die internet aan? ($_)" }
Expand-Archive $zip -DestinationPath $tmp -Force
$src = Get-ChildItem $tmp -Directory | ForEach-Object { Join-Path $_.FullName $AppDir } | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $src) { Fail "Gameshow sagteware nie in die aflaai gevind nie." }
New-Item -ItemType Directory -Force $Dest | Out-Null
# Copy the software; never overwrite the videos (vid\) or the saved scores (scores.json)
Get-ChildItem $src -Force | Where-Object { $_.Name -notin @("vid", "scores.json") } |
    ForEach-Object { Copy-Item $_.FullName (Join-Path $Dest $_.Name) -Recurse -Force }
foreach ($d in "vid\vrae", "vid\countdown", "vid\visual") { New-Item -ItemType Directory -Force (Join-Path $Dest $d) | Out-Null }
$scores = Join-Path $Dest "scores.json"
if (-not (Test-Path $scores)) {
    $z = [ordered]@{}; 1..12 | ForEach-Object { $z["$_"] = 0 }
    ($z | ConvertTo-Json -Compress) | Set-Content -Encoding ascii $scores
}
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
Ok "Sagteware in $Dest"

# 5. Python packages the gameshow needs
Step 5 "Python pakkette (kan 'n paar minute vat)"
& $Python -m pip install --disable-pip-version-check --upgrade pip | Out-Null
& $Python -m pip install --disable-pip-version-check -r (Join-Path $Dest "requirements.txt")
if ($LASTEXITCODE -ne 0) { Fail "Python pakkette kon nie installeer nie." }
Ok "Pakkette geinstalleer"

# 6. Check everything loads (VLC must match Python's 64-bit)
Step 6 "Toets"
$check = & $Python -c "import vlc, pygame, pynput, keyboard, win32gui, psutil, websockets; print('VLC', vlc.libvlc_get_version().decode())" 2>&1
if ($LASTEXITCODE -ne 0) { Fail "Toets het misluk: $check" }
Ok "$check"

# 7. Desktop shortcuts
Step 7 "Snelkoppelings op die lessenaar"
$desk = if ($env:GAMESHOW_SHORTCUTS) { $env:GAMESHOW_SHORTCUTS } else { [Environment]::GetFolderPath("Desktop") }
$sh = New-Object -ComObject WScript.Shell
$l = $sh.CreateShortcut((Join-Path $desk "Gameshow.lnk"))
$l.TargetPath = Join-Path $Dest "launch.bat"; $l.WorkingDirectory = $Dest; $l.Save()
$l = $sh.CreateShortcut((Join-Path $desk "Gameshow Netwerk.lnk"))
$l.TargetPath = "powershell.exe"
$l.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $Dest 'gameshow_network.ps1')`""
$l.WorkingDirectory = $Dest; $l.Save()
$l = $sh.CreateShortcut((Join-Path $desk "Gameshow Videos.lnk"))
$l.TargetPath = Join-Path $Dest "vid"; $l.Save()
Ok "Gameshow, Gameshow Netwerk, Gameshow Videos"

$nv = (Get-ChildItem (Join-Path $Dest "vid\vrae") -Filter *.mp4 -ErrorAction SilentlyContinue).Count
Write-Host "`nKLAAR! Die gameshow is geinstalleer." -ForegroundColor Green
Write-Host @"

Volgende stappe:
  1. Videos: pak die video-zip uit en kopieer vrae\, countdown\ en visual\
     in die 'Gameshow Videos' vouer op die lessenaar. (Nou: $nv vraag-videos.)
  2. Prop die kabel van die GameShow router in en dubbelklik 'Gameshow Netwerk'.
  3. Dubbelklik 'Gameshow' om te begin (toegangskode 00000).
"@
if (-not $env:GAMESHOW_NOPAUSE) { Read-Host "Druk Enter om toe te maak" }
