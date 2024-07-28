# Extract certificate data files from BGW210 and BGW320 routers

This repository exists to retrieve and convert calibration data from BGW routers. This data must be converted into `wpa_supplicant` compatible configuration files / certificates using [mfg_dat_decode](https://www.devicelocksmith.com/2018/12/eap-tls-credentials-decoder-for-nvg-and.html) from devicelocksmith (aka dls).

> [!CAUTION]
> This method requires downgrading firmware to earlier versions. That may result in configuration incompatibilities, which can result in the loss of various settings on the BGW.
> Though it _should_ remain be usable for internet access, this has not been tested. **Use at your own risk**.

## How is this different from mozzarellathicc/attcerts?

This script practically solves the identical problem that <https://github.com/mozzarellathicc/attcerts> solves. The key differences are:

1. Support for the BGW320.
2. Updated documentation for a downgrade path for the 210.
3. Faster operation. The extraction method (in both attcerts and this repo) utilizes a CVE in earlier firmware versions to obtain the raw certificate data from a partition that is only momentarily mounted on startup. Parallelized Python allows faster brute forcing to increase the probability of success. In most situations this script should retrieve the data in under 5 minutes with about 2-3 reboots.

## Requirements

- A BGW320 or BGW210 with compatible firmware (see below).
- A computer with a network interface card.
- Python 3.12 or later.

> [!NOTE]
> A virtual machine may be used. However, it may take longer for this script to work due to timing related issues.

## STEP 1: BGW preparation

To run the downloader, your BGW has to be on a compatible firmware. Version 3.18.1 is known to work with both BGW210 and BGW320. Firmware updates are performed via the BGW webui under the "diagnostics" tab -> "update" section.

### BGW210 downgrade path

Apply the following firmware images. **It is important that these firmware images are installed in the order they are displayed below**

1. First install: <http://gateway.c01.sbcglobal.net/firmware/ALPHA/210/001E46/BGW210-700_debug/spTurquoise210-700_2.14.2_NO_AT.bin>
2. Next, install: <http://gateway.c01.sbcglobal.net/firmware/ALPHA/210/001E46/BGW210-700_3.18.1/spTrapeze_Turquoise210-700_3.18.1.bin>

### BGW320 downgrade path

Depending on your device manufacturer, there are two separate download paths. You can determine your manufacturer by looking at the sticker on the back of the BGW320. **It is important that these firmware images are installed in the order they are displayed below**.

- BGW320-500 (Humax)

  1. First install: <http://gateway.c01.sbcglobal.net/firmware/ALPHA/320/0C08B4/BGW320-500_3.17.5_dnvpnP/spTurquoise320-500_3.17.5_dnvpnP_021_sec.bin>
  2. Next, install: <http://gateway.c01.sbcglobal.net/firmware/ALPHA/320/0C08B4/BGW320-500_3.18.1/spTurquoise320-500_3.18.1_sec.bin>

- BGW320-505 (Nokia)
  1. First install: <http://gateway.c01.sbcglobal.net/firmware/ALPHA/320/207852/BGW320-505_3.17.5_dnvpnP/spTurquoise320-505_3.17.5_dnvpnP_021_sec.bin>
  2. Next, install: <http://gateway.c01.sbcglobal.net/firmware/ALPHA/320/207852/BGW320-505_3.18.1/spTurquoise320-505_3.18.1_sec.bin>

## STEP 2: Physical preparation

It is best to use a physical machine to ensure the fastest possible operation. Virtual machines may require a few more reboots due to the timing nature of the method used by this script.

1. Connect your machine directly to LAN1 on the BGW.
2. Unplug any other SFP/ethernet cables plugged into the BGW (e.g., unplug the ONT port or remove the SFP adapter if fiber is supplied directly to the BGW).
3. Configure the NIC on your machine that is connected to LAN1 on the BGW with a static IP of 192.168.1.11, broadcast 255.255.255.0 and gateway 192.168.1.254. Ensure there are no other routes on to the 192.168.1/24 subnet available to your machine.

## STEP 3: Extraction

With your machine connected to LAN1 on the BGW and the BGW powered ON, perform the following:

1. Run the download.py script with **Python 3.12 or later**:

   ```bash
   python download.py
   ```

2. Let the script determine your BGW compatibility.
3. Follow the instructions in the terminal from the script.

## STEP 4: Conversion to wpa_supplicant-compatible configuration files

Use the appropriate version of [mfg_dat_decode](https://www.devicelocksmith.com/2018/12/eap-tls-credentials-decoder-for-nvg-and.html) with the resulting mfg.dat/calibration_01.bin and root certs produced by this script.

## STEP 5: Cleanup

You can upgrade your BGW to the latest firmware version when it is complete. These are latest as of July 28, 2024. Links to the latest images change often as firmware updates change but are not difficult to guess / find in online forums.

- BGW210-700: <http://gateway.c01.sbcglobal.net/firmware/GA/210/001E46/BGW210-700_4.28.6/spTurquoise210-700_4.28.6.bin>
- BGW320-500 (Humax): <http://gateway.c01.sbcglobal.net/firmware/GA/320/0C08B4/BGW320-500_4.27.7/spTurquoise320-500_4.27.7_sec.bin>
- BGW320-500 (Nokia): <http://gateway.c01.sbcglobal.net/firmware/GA/320/207852/BGW320-505_4.27.7/spTurquoise320-505_4.27.7_sec.bin>
