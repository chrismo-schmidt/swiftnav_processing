RTK GNSS Data Processing for SwiftNav
==============================

This package automized extracting the binary GNSS data logs created by SwiftNav GNSS devices and applying RTK corrections using RTKLib. It automatically downloads correction data and consecutively executes `sbp2rinex`, `sbp2report` and `rnx2rtkp`, creating an all-in-one postprocessing pipeline. 

## Disclaimer

This project is research code under development. It may contain bugs and sections of unused or insensible code as well as undocumented features. Major changes to this package are planned for the time to come. A proper API documentation is still missing. 

This project is an independent software solution and is **not affiliated with**, **endorsed by**, or **supported by** [Swift Navigation, Inc.](https://www.swiftnav.com/) All trademarks and product names are the property of their respective owners.  

## Requirements

- `spb2rinex` >= v2.3 ([from SwiftNav Ressource Library](https://www.swiftnav.com/resource-library?title=sbp2rinex&product=sbp2rinex&release=Latest)).

- `spb2report` >= v2.8 ([from SwiftNav Ressource Library](https://www.swiftnav.com/resource-library?title=sbp2rinex&product=sbp2report&release=Latest)).

- RTKLib >= 2.4.3 ([RTKLib website](https://www.rtklib.com/)).

## Installation

Install RTKLib.

1. Get the RTKLib binaries from [GitHub (tomojitakasu/RTKLIB)](https://github.com/tomojitakasu/RTKLIB_bin/tree/rtklib_2.4.3).

2. Add the binaries to your PATH variable.

Install `spb2rinex` and `sbp2report`.

1. Get the binaries from the [SwiftNav Ressource Library](https://www.swiftnav.com/resource-library).

2. Add the binaries to your PATH variable.

Install`batch_sbp2pos`.

1. Clone this repository. 

    `git clone https://github.com/chris-konrad/rtkprocessing.git`

2. Install the package and it's dependencies. Refer to `pyproject.toml` for an overview of the dependencies. 

   ```
   cd ./rtkprocessing
   pip install . 
   ```

Need help adding something to the PATH variable? Try [this guide](https://helpdeskgeek.com/windows-10/add-windows-path-environment-variable/) (or any other internet search result).

## Correction Data

The program automatlically downloads RTK GNSS correction data from the [Dutch Permanent GNSS Array (DPGA)](https://gnss1.tudelft.nl/dpga/). 
Per default, it opens an anonymous connection to `ftp://gnss1.tudelft.nl/` and downloads highrate RINEX data from the `DELF00NLD` station on the EwI tower at TU Delft campus. After processing, the downloaded correction data is deleted and only a correction log file is retained. To keep correction data, use `--keepcorrectiondata`.

The host adress (`--ftphost`) and GNSS base station (`--station`) can be configured manually. Note, however, that filenames are currently hard-coded to the format used by the DPGA, limiting the compatibility to data from DPGA stations younger then 2016. 

## RTKLib Config

RTKLib needs a config file for RTK GNSS correction. To create a custom config file for your needs, run `rtkpost.exe` from the RTKLib binaries and click *<u>O</u>ptions...* . After choosing the desired configuration, hit *<u>S</u>ave...* and save the config file to `DATA_DIRECTORY/` using the file ending `*.conf`. 

An [example configuration file](https://github.com/chris-konrad/rtkprocessing/blob/main/config/rtklib-swiftnav.conf) for SBP-files created by the SWIFTNav Piksi Multi v2 is provided in this repository. 

## Usage
The program automatically walks a folder tree, finds all directories containing .sbp files, downloads correction data, performs RTK-GNSS correction and exports the results to .pos. 

To run the program open a command prompt and execute the following:

`rtkprocessing [-h] --dir DIR [--ftphost FTPHOST] [--corrdir CORRDIR] [--station STATION] [--rtkconfig RTKCONFIG] [--connect] `

#### Options:

```
  -h, --help             Show this help message and exit.
  --dir DIR              Root directory. All directories containing .sbp below this directory will be processed.
  --outdir DIR           Root directory of the output. If given, the subfolder structure of the root directory is repeated in the output directory and results are stored in the corresponding subfolders.. If not specified, the output is stored in the root directory. 
  --ftphost FTPHOST      FTP host to download correction data from. Must accept anonymous connections. The default is gnss1.tudelft.nl.
  --corrdir CORRDIR      Use a global correction data directory shared across all SBP directories; correction data is never deleted and --keepcorrectiondata is ignored."
  --keepcorrectiondata   Keep correction data after processing each SBP directory; only applies when --corrdir is not used.
  --station STATION      The base station to download data from. The default is the EWI-tower (DELF00NLD).
  --connect              Suppress prompt asking for connection when downloading correction data.
  --rtkconfig RTKCONFIG  Specify the RTKLib config file. If not specified, the correction data directory is searched for a *.conf file.
```

#### Notes:
- `.sbp` for whom RTK correction results already exist are skipped.

#### Output:

After completion of `.sbp`-file decoding and RTK GNSS correction, `rtkprocessing` stores the results and intermediate results in three new subdirectories next to each `.sbp` file. If `--outdir` is supplied, the a filesystem identically to the filesystem in `--dir` will be created and outputs appear in the corresponding subdirectories:

- `report/` Contains the output of `sbp2report`, including trajectory plots, IMU data, Google Earth files and system logs. 

- `rinex/` Contains the output of `sbp2rinex`, including the `.nav` and `.obs` files corresponding to the sbp logs.

- `solution/` Contains the RTKLib output with the corrected GNSS data in the form of `.pos` files. These files can be interpreted by any text editor and contain the corrected position trajectories corresponding to the sbp logs. 

- `correction/` If `--keepcorrectiondata` and no correction data directory supplied, this directory contains the correction data. 

Additionally, a log-file detailing the used correction data and a plot of the raw and processed lat/lon data is stored in the top-level directory. 

## Old `batch_sbp2pos.bat`

This Python package is an elaborate update to the old bash script. It expands the scripts functions by automatically traversing directories and automatically downloading correction data. 

For reference, the old bash script is still available in [`scripts/`](https://github.com/chris-konrad/rtkprocessing/blob/main/scripts/)

## Authors

- Christoph M. Konrad, c.m.konrad@tudelft.nl

License
--------------------

This software is licensed under the terms of the [MIT license](https://github.com/chris-konrad/rtkprocessing/blob/main/LICENSE).
