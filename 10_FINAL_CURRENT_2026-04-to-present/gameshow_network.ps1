# Gameshow network setup (run via the "Gameshow Netwerk" desktop shortcut)
#
# The button units connect to 192.168.8.160 on the GameShow router.
# Plug a network cable from a LAN port on the GameShow router into this laptop,
# then run this: it gives the CABLE port that address. Wi-Fi is not touched,
# so the laptop keeps its normal internet.
#
#   gameshow_network.ps1          -> set the cable port to 192.168.8.160
#   gameshow_network.ps1 -Undo    -> put the cable port back to automatic (DHCP)

param([switch]$Undo)

$GameshowIP = "192.168.8.160"
$Prefix = 24

# Re-launch as Administrator (changing an IP address needs it)
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
         ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    $a = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    if ($Undo) { $a += " -Undo" }
    Start-Process powershell -Verb RunAs -ArgumentList $a
    exit
}

function Pause-Exit($code) { Write-Host ""; Read-Host "Druk Enter om toe te maak"; exit $code }

# The wired (cable) adapter: physical, not Wi-Fi / Bluetooth / virtual
$wired = Get-NetAdapter -Physical -ErrorAction SilentlyContinue |
    Where-Object { $_.MediaType -eq "802.3" -and $_.InterfaceDescription -notmatch "Bluetooth|Virtual|VPN|Hyper-V" } |
    Sort-Object @{e = { $_.Status -eq "Up" }; Descending = $true } | Select-Object -First 1
if (-not $wired) {
    Write-Host "Geen kabel-netwerkpoort (Ethernet) op hierdie rekenaar gevind nie." -ForegroundColor Red
    Write-Host "Gebruik 'n USB-Ethernet adapter, of skakel Wi-Fi na die GameShow netwerk."
    Pause-Exit 1
}
Write-Host "Kabelpoort: $($wired.Name) ($($wired.InterfaceDescription)) - status $($wired.Status)"

if ($Undo) {
    Set-NetIPInterface -InterfaceIndex $wired.ifIndex -Dhcp Enabled
    Get-NetIPAddress -InterfaceIndex $wired.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.PrefixOrigin -eq "Manual" } | Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Kabelpoort is terug op outomaties (DHCP)." -ForegroundColor Green
    Pause-Exit 0
}

if ($wired.Status -ne "Up") {
    Write-Host "Let wel: die kabel is nie ingeprop nie (of die router is af). Die adres word tog ingestel." -ForegroundColor Yellow
}
# No gateway on purpose: internet keeps going over Wi-Fi
Get-NetIPAddress -InterfaceIndex $wired.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
Set-NetIPInterface -InterfaceIndex $wired.ifIndex -Dhcp Disabled
New-NetIPAddress -InterfaceIndex $wired.ifIndex -IPAddress $GameshowIP -PrefixLength $Prefix | Out-Null
Start-Sleep -Seconds 2
$now = (Get-NetIPAddress -InterfaceIndex $wired.ifIndex -AddressFamily IPv4).IPAddress
Write-Host "Kabelpoort adres: $now" -ForegroundColor Green
if (Test-Connection 192.168.8.1 -Count 1 -Quiet) {
    Write-Host "GameShow router antwoord - gereed vir die knoppies." -ForegroundColor Green
} else {
    Write-Host "GameShow router antwoord nog nie (is die kabel in 'n LAN-poort van die router?)." -ForegroundColor Yellow
}
Pause-Exit 0
