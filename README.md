RTK GNSS Data Processing for SwiftNav
==============================

This is a working repostory for processing the binary GNSS data logs created by SwiftNav GNSS devices. It provides a script for batch `.sbp`-file decoding (currently Windows only) and RTK correction using RTKlib. It consecutively executes `sbp2rinex`, `sbp2report` and `rnx2rtkp`, creating an all-in-one postprocessing pipeline. 

### Disclaimer

The package is research code under development. It may contain bugs and sections of unused or insensible code as well as undocumented features. Major changes to this package are planned for the time to come. A proper API documentation is still missing. 

### Requirements

- `spb2rinex` >= v2.3 ([from SwiftNav Ressource Library](https://www.swiftnav.com/resource-library?title=sbp2rinex&product=sbp2rinex&release=Latest))

- `spb2report` >= ([from SwiftNav Ressource Library](https://www.swiftnav.com/resource-library?title=sbp2rinex&product=sbp2report&release=Latest))

- RTKLib >= 2.4.3 ([RTKLib website](https://www.rtklib.com/))

- A Windows OS.

## Installation

Install RTKLib

1. Get the RTKLib binaries from [GitHub (tomojitakasu/RTKLIB)](https://github.com/tomojitakasu/RTKLIB_bin/tree/rtklib_2.4.3)

2. Add the binaries to your PATH variable.

Install `spb2rinex` and `sbp2report`.

1. Get the binaries from the [SwiftNav Ressource Library](https://www.swiftnav.com/resource-library)

2. Add the binaries to your PATH variable.

Install`batch_sbp2pos`.

1. Clone this repository. 

    `git clone https://github.com/chrismo-schmidt/swiftnav_processing.git`

2. Add `PATH-TO-THIS-REPO/swiftnav_processing/sbp_decoding/` to your PATH variable. Replace `PATH-TO-THIS-REPO` with the absolute Path to the the location where you cloned this repo to

Need help adding something to the PATH variable? Try [this guide](https://helpdeskgeek.com/windows-10/add-windows-path-environment-variable/) (or any other internet search result).

### Usage

To run batch `.sbp` file processing, open a command prompt and execute

`batch_sbp2pos DATA_DIRECTORY`

The has to point towards a directory that contains any number of `.sbp` logfiles created by a SWIFTNav RTK GNSS and RTK GNSS correction data. The skript automatically processes all `.sbp` files it finds using all available correction data a `./correction_data` subdirectory.

 The skrip expects the following file structure:

```
DATA_DIRECTORY
├── correction_data
│   ├── rtklib-swiftnav.conf
│   ├── *.crx
│   ├── ...
│   └── *.crx
├── *.sbp
├── ...
└── *.sbp
```

#### Acquiring GNSS data

Create `.sbp` data with a SWIFTNav RTK GNSS (for example the Piksi Multi) following [SWIFTNav's documentation](https://support.swiftnav.com/support/solutions/folders/44001204965)

#### Acquiring correction data

Correction data can be obtained from a nearby permanent fixed GNSS arrays. In the Netherlands, this service is provided by the Dutch Permanent GNSS Array (DPGA). TU Delft operates a station on the roof of the EWI building. RINEX correction data can be obtained from https://gnss1.tudelft.nl/dpga/

#### Creating a RTKLib Config File

RTKLib need a config file for RTK GNSS correction. To create a custom config file for your needs, run `rtkpost.exe` from the RTKLib binaries and click *<u>O</u>ptions...* . After choosing the desired configuration, hit *<u>S</u>ave...* and save the config file to `DATA_DIRECTORY/correction_data/` using the filename `rtklib-swiftnav.conf`. 

An [example configuration file](https://github.com/chrismo-schmidt/swiftnav_processing/blob/main/sbp_processing/rtklib-swiftnav.conf) for SBP-files created by the SWIFTNav Piksi Multi v2 is provided in this repository. 

### Output

After completion of `.sbp`-file decoding and RTK GNSS correction, `batch_sbp2pos` stores the results and intermediate results in three new subdirectories to `DATA_DIRECTORY`:

- `report/` Contains the output of `sbp2report`, including trajectory plots, IMU data, Google Earth files and system logs. 

- `rinex/` Contains the output of `sbp2rinex`, including the `.nav` and `.obs` files corresponding to the sbp logs.

- `solution/` Contains the RTKLib output with the corrected GNSS data in the form of `.pos` files. These files can be interpreted by any text editor and contain the 
  
  corrected position trajectories corresponding to the sbp logs. 

### Authors

- Christoph M. Schmidt, c.m.schmidt@tudelft.nl

License
--------------------

This software is licensed under the terms of the [MIT license](https://github.com/chrismo-schmidt/cyclistsocialforce/blob/main/LICENSE).
