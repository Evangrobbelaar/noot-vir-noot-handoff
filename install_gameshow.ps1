# ============================================================================
#  Noot-vir-Noot gameshow - one-command installer for a fresh Windows laptop
# ============================================================================
#  Open PowerShell and paste ONLY this one line (nothing else):
#
#    irm https://raw.githubusercontent.com/Evangrobbelaar/noot-vir-noot-handoff/gameshow-final/install_gameshow.ps1 | iex
#
#  Installs: Python 3.12, VLC (64-bit), the gameshow software and its Python
#  packages, into %USERPROFILE%\Gameshow, plus desktop shortcuts.
#  Uses winget when it works, otherwise downloads the installers directly.
#  The show VIDEOS are NOT installed: copy them into %USERPROFILE%\Gameshow\vid
#  (vrae\, countdown\, visual\) from the video zip.
#  Running it again UPDATES the software and keeps the videos and scores.
# ============================================================================

function Install-Gameshow {
    # Everything lives in this function so nothing leaks into the PowerShell
    # window, and a failure never closes the window (no 'exit').
    $ErrorActionPreference = "Continue"
    $ProgressPreference = "SilentlyContinue"        # much faster downloads in PowerShell 5
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $env:PYTHONHOME = $null; $env:PYTHONPATH = $null
    $env:PYGAME_HIDE_SUPPORT_PROMPT = "1"

    $Repo   = "Evangrobbelaar/noot-vir-noot-handoff"
    $Branch = if ($env:GAMESHOW_BRANCH) { $env:GAMESHOW_BRANCH } else { "gameshow-final" }
    $AppDir = "10_FINAL_CURRENT_2026-04-to-present"
    $Dest   = if ($env:GAMESHOW_DIR) { $env:GAMESHOW_DIR } else { Join-Path $env:USERPROFILE "Gameshow" }
    $PyUrl  = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
    $VlcUrl = "https://download.videolan.org/pub/videolan/vlc/3.0.21/win64/vlc-3.0.21-win64.exe"
    $Pf64   = if ($env:ProgramW6432) { $env:ProgramW6432 } else { $env:ProgramFiles }

    function Step($n, $msg) { Write-Host "`n[$n/8] $msg" -ForegroundColor Cyan }
    function Ok($msg)       { Write-Host "      OK: $msg" -ForegroundColor Green }
    function Info($msg)     { Write-Host "      $msg" }
    function Fail($msg)     { throw $msg }
    function Find-Python {
        foreach ($p in (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
                       (Join-Path $Pf64 "Python312\python.exe")) {
            if (Test-Path $p) { return $p }
        }
        return $null
    }
    function Find-Vlc { Test-Path (Join-Path $Pf64 "VideoLAN\VLC\libvlc.dll") }
    function Download($url, $out) {
        for ($i = 1; $i -le 3; $i++) {
            try { Invoke-WebRequest $url -OutFile $out -UseBasicParsing -ErrorAction Stop; return }
            catch { if ($i -eq 3) { Fail "Kon nie aflaai nie: $url ($_). Is die internet aan?" }; Start-Sleep 3 }
        }
    }

    Write-Host "Noot-vir-Noot gameshow installer" -ForegroundColor Yellow
    Write-Host "Installeer na: $Dest"
    $tmp = Join-Path $env:TEMP ("gameshow_install_" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force $tmp | Out-Null
    $winget = [bool](Get-Command winget -ErrorAction SilentlyContinue)

    # 1. Internet
    Step 1 "Internet"
    try { Invoke-WebRequest "https://github.com" -UseBasicParsing -Method Head -TimeoutSec 20 -ErrorAction Stop | Out-Null }
    catch { Fail "Geen internet nie (kan nie github.com bereik nie). Koppel aan die internet en probeer weer." }
    Ok "internet werk"

    # 2. Python 3.12 (64-bit, for this user - no admin needed)
    Step 2 "Python 3.12"
    $Python = Find-Python
    if (-not $Python -and $winget) {
        Info "installeer met winget..."
        winget install -e --id Python.Python.3.12 --scope user --silent --source winget --accept-package-agreements --accept-source-agreements | Out-Host
        $Python = Find-Python
    }
    if (-not $Python) {
        Info "laai Python direk af van python.org..."
        $exe = Join-Path $tmp "python-3.12.10-amd64.exe"
        Download $PyUrl $exe
        Start-Process $exe -ArgumentList "/quiet InstallAllUsers=0 PrependPath=0 Include_launcher=0 Include_test=0" -Wait
        $Python = Find-Python
    }
    if (-not $Python) { Fail "Python kon nie installeer nie." }
    Ok ((& $Python --version 2>&1) -join " ")

    # 3. VLC media player, 64-bit (plays the videos; Windows may ask permission)
    Step 3 "VLC media player (64-bit)"
    if (-not (Find-Vlc) -and $winget) {
        Info "installeer met winget (Windows kan toestemming vra - kies Yes/Ja)..."
        winget install -e --id VideoLAN.VLC --architecture x64 --silent --source winget --accept-package-agreements --accept-source-agreements | Out-Host
    }
    if (-not (Find-Vlc)) {
        Info "laai VLC direk af van videolan.org (Windows kan toestemming vra - kies Yes/Ja)..."
        $exe = Join-Path $tmp "vlc-3.0.21-win64.exe"
        Download $VlcUrl $exe
        Start-Process $exe -ArgumentList "/L=1033 /S" -Verb RunAs -Wait
    }
    if (-not (Find-Vlc)) { Fail "VLC kon nie installeer nie. Installeer VLC 64-bit van videolan.org en probeer weer." }
    Ok "VLC gevind"

    # 4. The gameshow software (downloaded from GitHub; no git needed)
    Step 4 "Laai die gameshow sagteware af"
    # Only the gameshow folder (~0.3 MB), file by file, pinned to one commit.
    # Falls back to the whole project zip (~42 MB) if GitHub's file list is unavailable.
    $src = $null
    try {
        $commit = (Invoke-RestMethod "https://api.github.com/repos/$Repo/branches/$Branch" -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop).commit.sha
        $tree = Invoke-RestMethod "https://api.github.com/repos/$Repo/git/trees/$($commit)?recursive=1" -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop
        $files = @($tree.tree | Where-Object { $_.type -eq "blob" -and $_.path.StartsWith("$AppDir/") })
        if ($files.Count -gt 0) {
            $app = Join-Path $tmp "app"
            $i = 0
            foreach ($f in $files) {
                $i++
                $rel = $f.path.Substring($AppDir.Length + 1)
                Info "[$i/$($files.Count)] $rel"
                $out = Join-Path $app ($rel -replace "/", "\")
                New-Item -ItemType Directory -Force (Split-Path $out) | Out-Null
                Download "https://raw.githubusercontent.com/$Repo/$commit/$($f.path)" $out
            }
            $src = $app
        }
    } catch {
        if ("$_" -like "Kon nie aflaai nie*") { throw }
    }
    if (-not $src) {
        Info "laai die hele projek af (42 MB - kan 'n paar minute vat, wag asseblief)..."
        $zip = Join-Path $tmp "code.zip"
        Download "https://github.com/$Repo/archive/refs/heads/$Branch.zip" $zip
        Expand-Archive $zip -DestinationPath $tmp -Force -ErrorAction Stop
        $src = Get-ChildItem $tmp -Directory | ForEach-Object { Join-Path $_.FullName $AppDir } | Where-Object { Test-Path $_ } | Select-Object -First 1
    }
    if (-not $src) { Fail "Gameshow sagteware nie in die aflaai gevind nie." }
    New-Item -ItemType Directory -Force $Dest -ErrorAction Stop | Out-Null
    # Copy the software; never overwrite the videos (vid\) or the saved scores (scores.json)
    Get-ChildItem $src -Force | Where-Object { $_.Name -notin @("vid", "scores.json") } |
        ForEach-Object { Copy-Item $_.FullName (Join-Path $Dest $_.Name) -Recurse -Force -ErrorAction Stop }
    foreach ($d in "vid\vrae", "vid\countdown", "vid\visual", "vid\dance") { New-Item -ItemType Directory -Force (Join-Path $Dest $d) | Out-Null }
    $scores = Join-Path $Dest "scores.json"
    if (-not (Test-Path $scores)) {
        $z = [ordered]@{}; 1..12 | ForEach-Object { $z["$_"] = 0 }
        ($z | ConvertTo-Json -Compress) | Set-Content -Encoding ascii $scores
    }
    Ok "sagteware in $Dest"

    # 5. Python packages the gameshow needs
    Step 5 "Python pakkette (kan 'n paar minute vat)"
    & $Python -m pip install --disable-pip-version-check --upgrade pip 2>&1 | Out-Null
    $req = Join-Path $Dest "requirements.txt"
    & $Python -m pip install --disable-pip-version-check -r $req
    if ($LASTEXITCODE -ne 0) {
        Info "probeer weer..."
        & $Python -m pip install --disable-pip-version-check -r $req
        if ($LASTEXITCODE -ne 0) { Fail "Python pakkette kon nie installeer nie." }
    }
    Ok "pakkette geinstalleer"

    # 6. Check everything loads (VLC must match Python's 64-bit)
    Step 6 "Toets dat alles laai"
    $code = "import vlc, pygame, pynput, keyboard, win32gui, psutil, websockets; i = vlc.Instance(); assert i is not None, 'VLC'; print('VLC', vlc.libvlc_get_version().decode())"
    $check = & $Python -c $code 2>&1
    if ($LASTEXITCODE -ne 0) { Fail "Toets het misluk: $($check -join ' ')" }
    Ok (($check | Select-Object -Last 1) -as [string])

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

    # 8. Final check
    Step 8 "Finale kontrole"
    $bad = @()
    foreach ($f in "main.py", "video_player.py", "leaderboard.py", "server.py", "config.json", "launch.bat", "gameshow_network.ps1") {
        if (-not (Test-Path (Join-Path $Dest $f))) { $bad += $f }
    }
    foreach ($s in "Gameshow.lnk", "Gameshow Netwerk.lnk", "Gameshow Videos.lnk") {
        if (-not (Test-Path (Join-Path $desk $s))) { $bad += $s }
    }
    if ($bad) { Fail "Ontbreek: $($bad -join ', ')" }
    Ok "alle leers en snelkoppelings is daar"
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue

    $nv = @(Get-ChildItem (Join-Path $Dest "vid\vrae") -Filter *.mp4 -ErrorAction SilentlyContinue).Count
    $nc = @(Get-ChildItem (Join-Path $Dest "vid\countdown") -Filter *.mp4 -ErrorAction SilentlyContinue).Count
    Write-Host "`nKLAAR! Die gameshow is geinstalleer." -ForegroundColor Green
    Write-Host "Videos tans: $nv vraag-videos, $nc countdown-videos."
    Write-Host ""
    Write-Host "Volgende stappe:"
    Write-Host "  1. Videos: pak die video-zip uit en kopieer vrae\, countdown\, visual\ en dance\"
    Write-Host "     in die 'Gameshow Videos' vouer op die lessenaar."
    Write-Host "  2. Prop die kabel van die GameShow router in en dubbelklik 'Gameshow Netwerk'."
    Write-Host "  3. Dubbelklik 'Gameshow' om te begin (toegangskode 00000)."
}

try {
    Install-Gameshow
} catch {
    Write-Host "`nFOUT: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Maak 'n foto van hierdie skerm vir hulp." -ForegroundColor Red
}
if (-not $env:GAMESHOW_NOPAUSE) { Read-Host "`nDruk Enter om toe te maak" | Out-Null }
