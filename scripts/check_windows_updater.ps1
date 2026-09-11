param([Parameter(Mandatory=$true)][int]$AppPid)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$processCondition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $AppPid)
function Wait-Window($title) {
    $until = (Get-Date).AddSeconds(25)
    do {
        $windows = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $processCondition)
        foreach ($window in $windows) { if ($window.Current.Name -eq $title) { return $window } }
        Start-Sleep -Milliseconds 200
    } while ((Get-Date) -lt $until)
    throw "Window did not open: $title"
}
function Wait-Control($window, $names) {
    $until = (Get-Date).AddSeconds(25)
    do {
        $controls = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
        foreach ($control in $controls) { if ($names -contains $control.Current.Name) { return $control } }
        Start-Sleep -Milliseconds 200
    } while ((Get-Date) -lt $until)
    throw ('Control did not render: ' + ($names -join ', '))
}
$main = Wait-Window 'Skill-Desk'
$skipTour = Wait-Control $main @('Skip tour')
$skipTour.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
Write-Output 'First-launch walkthrough rendered and was dismissed.'
for ($attempt=1; $attempt -le 2; $attempt++) {
    $button = Wait-Control $main @('Updates', 'Update available')
    Write-Output "Attempt ${attempt}: opening Updates from the main webview"
    $button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    $updater = Wait-Window 'Skill-Desk updates'
    $null = Wait-Control $updater @('Check for updates')
    # The version appears only after JavaScript successfully calls native update_status.
    $until = (Get-Date).AddSeconds(25)
    $ready = $false
    do {
        $controls = $updater.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
        foreach ($control in $controls) { if ($control.Current.Name -like 'Installed version *') { $ready=$true; break } }
        if (!$ready) { Start-Sleep -Milliseconds 200 }
    } while (!$ready -and (Get-Date) -lt $until)
    if (!$ready) { throw 'Updater opened but its native status never rendered' }
    Write-Output "Attempt ${attempt}: updater content and native status rendered"
    $updater.GetCurrentPattern([System.Windows.Automation.WindowPattern]::Pattern).Close()
}
$null = Wait-Control $main @('Manage skills')
Write-Output 'Windows updater open, close, reopen and main-window responsiveness passed.'
