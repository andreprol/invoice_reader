Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
batPath = fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "executar.bat")
shell.Run Chr(34) & batPath & Chr(34), 0, False
