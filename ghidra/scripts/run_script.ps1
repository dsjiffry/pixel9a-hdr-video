# Usage: run_script.ps1 <tegu|comet> <ScriptName.java> <arg1> <arg2> ...
param([string]$prog, [string]$script, [Parameter(ValueFromRemainingArguments=$true)][string[]]$rest)
$R = Split-Path $PSScriptRoot -Parent
$env:JAVA_TOOL_OPTIONS = "-Dapplication.settingsdir=$R\settings_$prog -Dapplication.cachedir=$R\cache_$prog"
$env:JAVA_HOME = 'C:\OTHER\ghidra\jdk-25.0.5+8'; $env:GHIDRA_HEADLESS_MAXMEM = '8G'
$G = 'C:\OTHER\ghidra\ghidra_12.2_PUBLIC\support\analyzeHeadless.bat'
$name = [System.IO.Path]::GetFileNameWithoutExtension($script)
'' | & $G "$R\proj" $prog -process liblyric_hwl.so -noanalysis -readOnly -scriptPath "$R\scripts" -postScript $name @rest *> "$R\out\scriptrun_$prog.log"
"exit $LASTEXITCODE"
Get-Content "$R\out\scriptrun_$prog.log" | Select-String "ERROR|Exception" | Select-Object -First 5
