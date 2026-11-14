# Usage: run_grep.ps1 <tegu|comet> <outfile> <regex-without-spaces>
param([string]$prog, [string]$outf, [string]$rx)
$R = Split-Path $PSScriptRoot -Parent
$env:JAVA_TOOL_OPTIONS = "-Dapplication.settingsdir=$R\settings_$prog -Dapplication.cachedir=$R\cache_$prog"
$env:JAVA_HOME = 'C:\OTHER\ghidra\jdk-25.0.5+8'; $env:GHIDRA_HEADLESS_MAXMEM = '10G'
$G = 'C:\OTHER\ghidra\ghidra_12.2_PUBLIC\support\analyzeHeadless.bat'
'' | & $G "$R\proj" $prog -process liblyric_hwl.so -noanalysis -readOnly -max-cpu 7 -scriptPath "$R\scripts" -postScript GrepDecomp.java $outf $rx *> "$R\out\grep_$prog.log"
"exit $LASTEXITCODE"
Get-Content "$R\out\grep_$prog.log" | Select-String "functions:|matches:|ERROR|Exception" | Select-Object -First 8
