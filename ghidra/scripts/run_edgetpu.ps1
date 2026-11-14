# Import + analyze a stripped arm64 ELF, then GrepDecomp over it.
# Usage: run_edgetpu.ps1 <binaryPath> <regexFile> <outFile>
param([string]$bin, [string]$rxfile, [string]$out)
$R = Split-Path $PSScriptRoot -Parent
$env:JAVA_TOOL_OPTIONS = "-Dapplication.settingsdir=$R\settings_edgetpu -Dapplication.cachedir=$R\cache_edgetpu"
$env:JAVA_HOME = 'C:\OTHER\ghidra\jdk-25.0.5+8'; $env:GHIDRA_HEADLESS_MAXMEM = '8G'
$G = 'C:\OTHER\ghidra\ghidra_12.2_PUBLIC\support\analyzeHeadless.bat'
'' | & $G "$R\proj_edgetpu" edgetpu -import $bin -overwrite -scriptPath "$R\scripts" -postScript GrepDecomp.java $out "@$rxfile" *> "$R\out\run_edgetpu.log"
"exit $LASTEXITCODE"
Get-Content "$R\out\run_edgetpu.log" | Select-String "ERROR|Exception|functions:|matches:" | Select-Object -First 20
