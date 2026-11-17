using UnrealBuildTool;

public class PredioDroneEditorTarget : TargetRules
{
	public PredioDroneEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("PredioDrone");
	}
}
