# tgpcdx2dds

## Unpacking `.TgPcDx` files

Use the following command in PowerShell. Replace paths to the Railworks/TSC directory and the asset directory.

```ps1
$Serz="D:\Path\To\serz.exe";
$AssetRoot="D:\Path\To\Asset";
gci $AssetRoot -Recurse -File -Include *.TgPcDx | % { & $Serz $_.FullName "/xml:$($_.FullName).xml" }
```