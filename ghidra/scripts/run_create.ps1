param([string]$prog, [string]$list)
$R = Split-Path $PSScriptRoot -Parent
$env:JAVA_TOOL_OPTIONS = "-Dapplication.settingsdir=$R\settings_$prog -Dapplication.cachedir=$R\cache_$prog"
$env:JAVA_HOME = 'C:\OTHER\ghidra\jdk-25.0.5+8'; $env:GHIDRA_HEADLESS_MAXMEM = '10G'
$G = 'C:\OTHER\ghidra\ghidra_12.2_PUBLIC\support\analyzeHeadless.bat'
'' | & $G "$R\proj" $prog -process liblyric_hwl.so -noanalysis -scriptPath "$R\scripts" -postScript CreateFns.java $list *> "$R\out\create_$prog.log"
"exit $LASTEXITCODE"
Get-Content "$R\out\create_$prog.log" | Select-String "existing=|ERROR|Exception|Save" | Select-Object -First 6
