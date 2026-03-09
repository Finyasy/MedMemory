# MedMemoryPatient Xcode Project

This folder contains the XcodeGen specification and iOS configuration files for the native MedMemory patient app.

## Generate the Xcode project

```bash
cd /Users/bryan.bosire/anaconda_projects/MedMemory/ios/MedMemoryPatient
xcodegen generate
open MedMemoryPatient.xcodeproj
```

## Run on device

1. Open `MedMemoryPatient.xcodeproj` in Xcode.
2. Select the `MedMemoryPatient` target.
3. Set your Apple Developer team under `Signing & Capabilities`.
4. The default bundle identifier is `com.bryanbosire.medmemory.patient`. If your team still rejects it, change it to another unique reverse-DNS string.
5. Confirm the `HealthKit` capability is present.
6. Choose a real iPhone as the run destination.
7. Press `Run`.

## Backend note

Use your Mac LAN IP in the app `Sync` tab, not `localhost`.
