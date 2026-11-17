using UnrealBuildTool;

public class PredioDroneTarget : TargetRules
{
	public PredioDroneTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("PredioDrone");
	}
}
