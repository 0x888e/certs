# Extract certificate data files from BGW210 and BGW320 routers

Retrieves 802.1x certificate calibration data from BGW routers. This data must be converted into `wpa_supplicant` compatible configuration files / certificates using [mfg_dat_decode](https://www.devicelocksmith.com/2018/12/eap-tls-credentials-decoder-for-nvg-and.html) from devicelocksmith (aka dls).

> [!CAUTION]
> This method requires downgrading firmware to earlier versions. That may result in configuration incompatibilities, which can result in the loss of various settings on the BGW.
> Though it _should_ remain be usable for internet access, this has not been tested. It is not recommended to use this approach on a BGW provisioned for service. **Use at your own risk**.

**As of August 8, 2024, the official mirror of the firmware images listed below does not appear to host the images any longer. These images can still be obtained by separate mirrors from community-provided links, but are unofficial. If you use such a link, validate the images using the SHA1/MD5 hashes listed below (which were calculated from the official mirror images).**

## How is this different from mozzarellathicc/attcerts?

This script practically solves the identical problem that <https://github.com/mozzarellathicc/attcerts> solves. The key differences are:

1. Support for the BGW320.
2. Automatic BGW model detection.
3. Updated documentation for a downgrade path for the 210.
4. Faster, simpler operation. The extraction method (in both attcerts and this repo) utilizes a path traversal vulnerability in earlier firmware versions to obtain the raw certificate data from a partition that is only momentarily mounted on startup. Parallelized Python allows faster brute forcing to increase the probability of success. In most situations this script should retrieve the data in under 5 minutes with about 2-3 reboots.

## Requirements

- A BGW320 or BGW210 with compatible firmware (see below).
- A computer with a network interface card.
- Python 3.12 or later.

> [!NOTE]
> A virtual machine may be used. However, it may take longer for this script to work due to timing related issues.

## STEP 1: BGW preparation

To run the downloader, your BGW has to be on a compatible firmware. Version 3.18.1 is known to work with both BGW210 and BGW320. Firmware updates are performed via the BGW webui under the "diagnostics" tab -> "update" section.

> [!NOTE]
> **Your BGW210/BGW320 should not have internet access at this point.** Using a live provisioned device is not recommended. If you must, pull out the SFP adapter (BGW320) or, if you're using an external ONT, the ethernet cable from the RED ONT port (typical for the BGW210) after downloading these images, then flash with the device disconnected from the internet.

### BGW210 downgrade path

Apply the following firmware images. **It is important that these firmware images are installed in the order they are displayed below**

If the BGW210 has firmware version 4.28.6 or later:
  1. Install: <http://gateway.c01.sbcglobal.net/firmware/ALPHA/210/001E46/BGW210-700_3.18.2/spTurquoise210-700_3.18.2_ENG.bin>

> [!WARNING]
> There is at least one report of the inability to change firmware versions after flashing version 3.18.1 (listed below) on the BGW210

Alternate downgrade path (only use if the previous firmware could not be applied):
   1. First install: <http://gateway.c01.sbcglobal.net/firmware/ALPHA/210/001E46/BGW210-700_debug/spTurquoise210-700_2.14.2_NO_AT.bin>
      - SHA1: `e18115da88c3be8dd06806955f32e8b730407e8b`
      - MD5: `da46862eab89212439507b6e1792b2d1`
   3. Next, install: <http://gateway.c01.sbcglobal.net/firmware/ALPHA/210/001E46/BGW210-700_3.18.1/spTrapeze_Turquoise210-700_3.18.1.bin>
      - SHA1: `c2cafb7fb81e68238be938aed0e302e3b6522ef8`
      - MD5: `da1bd55bf48754823e75089baead74da`

### BGW320 downgrade path

Depending on your device manufacturer, there are two separate downgrade paths. You can determine your manufacturer by looking at the sticker on the back of the BGW320. **It is important that these firmware images are installed in the order they are displayed below**.

> [!WARNING]
> In at least two cases, these firmware versions are reported to have a finite (60-90 second) window before the BGW320 reboots. You will have to quickly flash the firmware version immediately when the webui first comes online. To aid in this process, it is advisable to ping the device in another window (`ping 192.168.1.254`). Ping will show the device online briefly, then offline, then online again. It is the second online window when you need to upload the firmware, so have the access code readily available when you browse to <http://192.168.1.254/cgi-bin/update.ha>.

- BGW320-500 (Humax)
  1. First install: <http://gateway.c01.sbcglobal.net/firmware/ALPHA/320/0C08B4/BGW320-500_3.17.5_dnvpnP/spTurquoise320-500_3.17.5_dnvpnP_021_sec.bin>
     - SHA1: `259e91b586f89f1e94eaa554a52fd9a2ea1cd026`
     - MD5: `7882823e14bbeef187e2754f49323f4c`
  3. Next, install: <http://gateway.c01.sbcglobal.net/firmware/ALPHA/320/0C08B4/BGW320-500_3.18.1/spTurquoise320-500_3.18.1_sec.bin>
     - SHA1: `790bdc528696885871505e025d5c0328595d4447`
     - MD5: `0d9f4b2a6139e92517884c26f5ed4f3b`

- BGW320-505 (Nokia)
  1. First install: <http://gateway.c01.sbcglobal.net/firmware/ALPHA/320/207852/BGW320-505_3.17.5_dnvpnP/spTurquoise320-505_3.17.5_dnvpnP_021_sec.bin>
     - SHA1: `0fd668617ff0a723379380a9f5d167f2a6015ef8`
     - MD5: `d3d9bc9d76d5331659176ae4cfe744af`
  3. Next, install: <http://gateway.c01.sbcglobal.net/firmware/ALPHA/320/207852/BGW320-505_3.18.1/spTurquoise320-505_3.18.1_sec.bin>
     - SHA1: `2e81363a1cc0784c82e3f5305668c88b49e33561`
     - MD5: `63d74cda47de1dde22303f1d99328803`

## STEP 2: Physical preparation

It is best to use a physical machine to ensure the fastest possible operation. Virtual machines may require a few more reboots due to the timing nature of the method used by this script.

1. Connect your machine directly to LAN1 on the BGW.
2. Unplug any other SFP/ethernet cables plugged into the BGW (e.g., unplug the ONT port or remove the SFP adapter if fiber is supplied directly to the BGW). **The ONLY cables plugged into the BGW should be the ethernet cable to your computer and the power cable**.
3. Configure the NIC on your machine that is connected to LAN1 on the BGW with a static IP of 192.168.1.11, broadcast 255.255.255.0 and gateway 192.168.1.254. Ensure there are no other routes on to the 192.168.1/24 subnet available to your machine.

## STEP 3: Extraction

With your machine connected to LAN1 on the BGW and the BGW powered ON, perform the following:

1. Run the download.py script with **Python 3.12 or later**:

   ```bash
   python download.py
   ```

2. Let the script determine your BGW compatibility.
3. Follow the instructions in the terminal from the script.

For the BGW320, four files will be produced: calibraiton_01.bin, and roughly three root CA der files.

For the BGW210, four files will be produced: mfg.dat, and roughly three (or more, varies based on the device) root CA der files.

## STEP 4: Conversion to wpa_supplicant-compatible configuration files

Use the appropriate version of [mfg_dat_decode](https://www.devicelocksmith.com/2018/12/eap-tls-credentials-decoder-for-nvg-and.html) with the resulting mfg.dat/calibration_01.bin and root certs produced by this script.

## STEP 5: Cleanup

You can upgrade your BGW to the latest firmware version when it is complete. These are latest as of July 28, 2024. Links to the latest images change often as firmware updates change but are not difficult to guess / find in online forums.

- BGW210-700: <http://gateway.c01.sbcglobal.net/firmware/GA/210/001E46/BGW210-700_4.28.6/spTurquoise210-700_4.28.6.bin>
- BGW320-500 (Humax): <http://gateway.c01.sbcglobal.net/firmware/GA/320/0C08B4/BGW320-500_4.27.7/spTurquoise320-500_4.27.7_sec.bin>
- BGW320-505 (Nokia): <http://gateway.c01.sbcglobal.net/firmware/GA/320/207852/BGW320-505_4.27.7/spTurquoise320-505_4.27.7_sec.bin>
