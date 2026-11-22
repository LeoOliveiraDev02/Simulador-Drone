# Atalho único "Simulador de Drone" na área de trabalho.
# Os atalhos antigos (Godot / "Drone - Predio em Obra") NÃO são apagados: vão para C:\drone\_antigos\atalhos
$exe = 'D:\DronePredio\jogo\Windows\PredioDrone.exe'
$sh = New-Object -ComObject WScript.Shell
$antigos = 'C:\drone\_antigos\atalhos'
New-Item -ItemType Directory -Force -Path $antigos | Out-Null
$mesas = @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('CommonDesktopDirectory')) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique
foreach ($m in $mesas) {
  Get-ChildItem -Path $m -Filter *.lnk -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.Name -like 'Simulador de Drone*') { return }
    $alvo = ''
    try { $l = $sh.CreateShortcut($_.FullName); $alvo = $l.TargetPath + ' ' + $l.Arguments + ' ' + $l.WorkingDirectory } catch {}
    $velho = ($_.Name -like 'Drone - Predio*') -or ($alvo -match 'PredioDrone') -or ($alvo -match '(?i)C:\\drone\\') -or ($alvo -match '(?i)voo_e88|VOAR_E88|godot')
    if ($velho) {
      try { Move-Item -Force $_.FullName (Join-Path $antigos $_.Name); "atalho antigo guardado em $antigos : " + $_.Name } catch { "nao consegui mover " + $_.Name }
    }
  }
}
$mesa = [Environment]::GetFolderPath('Desktop')
$lnk = Join-Path $mesa 'Simulador de Drone.lnk'
$s = $sh.CreateShortcut($lnk)
$s.TargetPath = $exe
$s.Arguments = '-NotInstalled'
$s.WorkingDirectory = 'D:\DronePredio\jogo\Windows'
$s.IconLocation = "$exe,0"
$s.Description = 'Simulador de Drone - Fazenda, Predio em Obra e Usina (Unreal 5.8 + AMD FSR 4)'
$s.Save()
"atalho: $lnk"
# vitrine de testes (assets novos, um de cada vez)
$lnk2 = Join-Path $mesa 'Simulador de Drone - Vitrine.lnk'
$v = $sh.CreateShortcut($lnk2)
$v.TargetPath = $exe
$v.Arguments = '-NotInstalled -mapa=Vitrine'
$v.WorkingDirectory = 'D:\DronePredio\jogo\Windows'
$v.IconLocation = "$exe,0"
$v.Description = 'Vitrine de testes: chao e arvores novos antes de ir para a fazenda'
$v.Save()
"atalho: $lnk2"
