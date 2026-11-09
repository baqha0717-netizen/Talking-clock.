# Соати гӯё 5.3.22

Signed Android 10+ talking clock by AMIN JON. Russian, Tajik and Persian recordings; Russian and Tajik interface. Install the APK over the existing version to preserve settings.

This update removes the screen-reader audio-track gate that could cancel manual, widget and scheduled speech after ten seconds. Enabling a reader during playback now releases the clock's focus while preserving its phrase. Reader sessions do not request global audio focus or change system volume. Wall-clock intervals are 5, 10, 15, 30 and 60 minutes.

266 JUnit tests and 285 service checks with simulated Android passed. Physical TalkBack/Jieshuo playback, locked-screen audio, installation and reboot have not been tested for this release.

The publication workflow verifies the approved payload's size and SHA256, reconstructs the signed APK and deterministic installation ZIP, validates the Android package/version and original signing certificate with apksigner, and uploads all assets through a draft release. It checks uploaded bytes before making the release latest, then checks public downloads. Existing published releases are immutable.

Only signed distributions, public metadata, notes and publication automation belong here. Owner-private source, signing keys and private diagnostic reports are excluded.
