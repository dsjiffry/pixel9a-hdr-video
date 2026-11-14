# Usage: run_decomp.ps1 <tegu|comet> <listfile>
param([string]$prog, [string]$list)
$R = Split-Path $PSScriptRoot -Parent
$env:JAVA_TOOL_OPTIONS = "-Dapplication.settingsdir=$R\settings_$prog -Dapplication.cachedir=$R\cache_$prog"
$env:JAVA_HOME = 'C:\OTHER\ghidra\jdk-25.0.5+8'; $env:GHIDRA_HEADLESS_MAXMEM = '8G'
$G = 'C:\OTHER\ghidra\ghidra_12.2_PUBLIC\support\analyzeHeadless.bat'
'' | & $G "$R\proj" $prog -process liblyric_hwl.so -noanalysis -readOnly -scriptPath "$R\scripts" -postScript DecompileFns.java "@$list" *> "$R\out\run_$prog.log"
"exit $LASTEXITCODE"
Get-Content "$R\out\run_$prog.log" | Select-String "ERROR|Exception" | Select-Object -First 5
