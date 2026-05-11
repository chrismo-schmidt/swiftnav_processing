
import os
import sys
import glob
import subprocess

import os
import pandas as pd
import numpy as np
import argparse

from datetime import datetime, timedelta

from ftplib import FTP
import gzip
import shutil
import warnings

def get_timespans(sbp_dir, report_subdir='report'):
    """ Extract the timespan of each sbp file form the corresponding report. Requires that sbp2report has run already."""

    timespans = []
    sbp_filenames = [os.path.splitext(f)[0] for f in os.listdir() if f.endswith(".sbp")]
    pattern = r"%Y-%m-%d %H:%M:%S.%f"

    for fname in sbp_filenames:
        fpath = os.path.join(sbp_dir, report_subdir, fname, fname+'.csv')
        if not os.path.isfile(fpath):
            raise FileNotFoundError(f"File {fpath} does not exist!")

        data = pd.read_csv(fpath)
        
        i0 = max(data['UTC Time'].first_valid_index(), data['UTC Date'].first_valid_index())
        i1 = min(data['UTC Time'].last_valid_index(), data['UTC Date'].last_valid_index())
        
        begin = f"{data['UTC Date'].iloc[i0]} {data['UTC Time'].iloc[i0]}"
        end = f"{data['UTC Date'].iloc[i1]} {data['UTC Time'].iloc[i1]}"

        span = (datetime.strptime(begin, pattern), datetime.strptime(end, pattern))
        timespans.append(span)

    return timespans


def make_corrfile_name(dt, station = 'DELF00NLD'):
    """Make the ftp filepath of the correction data file containing dt
    """

    closest = datetime(year=dt.year, month=dt.month, day=dt.day, hour=dt.hour, minute= 15 * np.floor(dt.minute/15).astype(int))
    timestr = closest.strftime(r"%Y%j%H%M")
    name = f'/{closest.year}/{closest.strftime("%j")}/{station}_R_{timestr}_15M_01S_MO.crx.gz'

    return name


def get_correction_filenames(sbp_dir, **kwargs):
    """ Get all ftp filepaths of required to """

    timespans = get_timespans(sbp_dir)

    correction_files = set()

    for span in timespans:
        dt_range = span[0]
        while dt_range < span[1]:
            correction_files.add(make_corrfile_name(dt_range, **kwargs))
            dt_range = dt_range + timedelta(minutes=15)

    return correction_files


def download_correction_files(files, host, download_dir, suppress_download_prompt=False):

    # Verify connection
    if not suppress_download_prompt:
        answer = input(f"Do you want to connect to ftp://{host} to download missing correction data? (Y/n)")
        
        if answer != "Y":
            print("Aborting.")
            sys.exit(1)

    print(f"Download target: {download_dir}")

    # Connect and login
    ftp = FTP(host)
    ftp.login(user="anonymous")
    #ftp.cwd("rinex/highrate/")

    try:
        for f_remote in files:
            f_local = os.path.join(download_dir,f_remote.split("/")[-1])

            # Download the file
            print(f"   Downloading {f_remote} ... ", end="")
            with open(f_local, "wb") as f:
                ftp.retrbinary(f"RETR rinex/highrate{f_remote}", f.write)
            print(f"done!")

            # Extract
            print(f"   Extracting {f_remote} ... ", end="")
            with gzip.open(os.path.join(download_dir, f_local), 'rb') as f_compressed:
                with open(os.path.join(download_dir, os.path.splitext(f_local)[0]), 'wb') as f_extracted:
                    shutil.copyfileobj(f_compressed, f_extracted)
            os.remove(os.path.join(download_dir, f_local))
            print(f"done!")

        print(f"Finished downloading {len(files)} correction files from {host}.")
    except Exception as e:
        ftp.quit()
        raise e


def process_sbp_files(sbp_dir, host, station, corr_dir=None, suppress_download_prompt=False, conf_file=None, keep_correction_data=False):
    print(f"Processing SBP files in {sbp_dir}:")

    # Define in-/output directories
    RINEX_OUT = "rinex"
    REPORT_OUT = "report"
    SOLUTION_OUT = "solution"
    CORR_IN = "correction"

    cwd = os.getcwd()

    # Check if directory exists
    if not os.path.exists(sbp_dir):
        print(f"The given directory does not exist: {sbp_dir}")
        sys.exit(1)

    # Check correction data directory
    if corr_dir is None:
        corr_dir = os.path.join(sbp_dir, CORR_IN)
        os.makedirs(corr_dir, exist_ok=True)
        local_correction_data = True
    else:
        if not os.path.exists(corr_dir):
            print(f"Couldn't find the specified correction data directory: {corr_dir}!")
            sys.exit(1)
        local_correction_data = False
    
    dir_correction_local = os.path.join(sbp_dir, CORR_IN)
    os.makedirs(dir_correction_local, exist_ok=True)

    # Create output directories
    for folder in [RINEX_OUT, REPORT_OUT, SOLUTION_OUT]:
        os.makedirs(os.path.join(sbp_dir, folder), exist_ok=True)

    # Change to sbp_dir
    os.chdir(sbp_dir)

    # Process each .sbp file
    sbp_files = [f for f in os.listdir() if f.endswith(".sbp")]
    if len(sbp_files)==0:
        print("No .sbp files found in the directory.")
        sys.exit(1)

    print("Extracting SBP files:")
    for sbp_file in sbp_files:
        fname_no_ext = os.path.splitext(sbp_file)[0]
        print(f"\n{fname_no_ext}\n----------")

        # Convert SBP to RINEX
        exists = [os.path.isfile(os.path.join(sbp_dir, RINEX_OUT, f"{fname_no_ext}{ftype}")) for ftype in [".nav", ".obs", ".sbs"]]
        if not np.all(exists):
            print("\nConverting SBP to RINEX ... ")
            subprocess.run(["sbp2rinex", os.path.join(sbp_dir, sbp_file), "-d", os.path.join(sbp_dir, RINEX_OUT)], check=True)
            print("done!")
        else:
            print("\nFound existing RINEX ... ")

        # Generate report
        exists = [os.path.isfile(os.path.join(sbp_dir, REPORT_OUT, fname_no_ext, f"{fname_no_ext}{ftype}")) for ftype in [".csv", "-ins.csv", "-msg.csv", "-trk.csv"]]
        if not np.all(exists):
            print("\nGenerating report ... ")
            os.chdir(os.path.join(sbp_dir, REPORT_OUT))
            subprocess.run(["sbp2report", "-d", os.path.join(sbp_dir, sbp_file)], check=True)
            os.chdir(sbp_dir)
            print("done!")
        else:
            print("\nFound existing report ... ")

    # Download correction data
    corr_filenames = get_correction_filenames(sbp_dir)
    corr_filenames_missing = [cfname for cfname in corr_filenames if not os.path.isfile(os.path.join(corr_dir, os.path.splitext(cfname.split("/")[-1])[0]))]
    corr_filenames_missing.sort()
    corr_filenames_existing = [cfname.split("/")[-1] for cfname in corr_filenames if os.path.isfile(os.path.join(corr_dir, os.path.splitext(cfname.split("/")[-1])[0]))]
    corr_filenames_existing.sort()
    if len(corr_filenames_existing) > 0:
        print(f"Found {len(corr_filenames_existing)}/{len(corr_filenames)} required correction data files.")
        for cfname in corr_filenames_existing:
            print(f"   {os.path.splitext(cfname)[0]}")
    if len(corr_filenames_missing) > 0:
        print(f"Missing {len(corr_filenames_missing)}/{len(corr_filenames)} required correction data files.")
        download_correction_files(corr_filenames_missing, host, corr_dir, suppress_download_prompt=suppress_download_prompt)
    files_downloaded = [os.path.basename(f) for f in corr_filenames_missing]
    files_existing = corr_filenames_existing
    files_used = sorted(
        set(files_existing + [os.path.basename(f) for f in corr_filenames_missing])
    )

    # Check for .conf file
    if conf_file is None:
        conf_files = glob.glob(os.path.join(sbp_dir, "*.conf"))
        if not conf_files:
            print(f"No .conf file found in {sbp_dir}")
            sys.exit(1)
        conf_file = conf_files[0]
        if len(conf_files)>1:
            warnings.warn(f"More then one config file in '{sbp_dir}'! Using first.")
    print(f"Using config file: {conf_file}")
    
    print("Apply RTK corrections:")
    for sbp_file in sbp_files:
    
        fname_no_ext = os.path.splitext(sbp_file)[0]
        print(f"{fname_no_ext} ... ", end="")

        # Apply RTK corrections
        pos_output = os.path.join(sbp_dir, SOLUTION_OUT, f"{fname_no_ext}.pos")
        obs_file = os.path.join(sbp_dir, RINEX_OUT, f"{fname_no_ext}.obs")
        nav_file = os.path.join(sbp_dir, RINEX_OUT, f"{fname_no_ext}.nav")
        if os.path.isfile(pos_output):
            print("Found existing .pos file. Skip!")
            continue

        subprocess.run([
            "rnx2rtkp",
            "-k", conf_file,
            "-o", pos_output,
            obs_file,
            os.path.join(corr_dir, "*.crx"),
            nav_file
        ], shell=True, check=True)
        print(f"output: {pos_output}, done!")
    
    
    # log correction 
    files_deleted = (
        files_used if local_correction_data and not keep_correction_data else []
    )
    remote_folders = sorted(
        {
            os.path.join("rinex", "highrate", os.path.dirname(f).lstrip("/"))
            for f in corr_filenames_missing
        }
    )

    write_correction_log(
        dir_correction_local=dir_correction_local,
        sbp_dirname=os.path.basename(sbp_dir),
        rtk_conf_name=os.path.basename(conf_file),
        correction_mode="local" if local_correction_data else "global",
        ftp_host=host if files_downloaded else None,
        ftp_remote_dir=", ".join(remote_folders) if remote_folders else None,
        files_used=files_used,
        files_downloaded=files_downloaded,
        files_deleted=files_deleted,
    )

    # Delete correction data
    if local_correction_data and not keep_correction_data:
        print(f"Deleting correction data in {corr_dir}")
        for fname in os.listdir(corr_dir):
            if fname.endswith(".crx") or fname.endswith(".crx.gz"):
                os.remove(os.path.join(corr_dir, fname))

    # Return to original directory
    os.chdir(cwd)
    print(f"Finished! Results are in {os.path.join(sbp_dir, SOLUTION_OUT)}")


def get_sbp_dirs(root_dir):
    sbp_dirs = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Check if any file in this directory ends with .sbp
        if any(fname.lower().endswith(".sbp") for fname in filenames):
            sbp_dirs.append(dirpath)

    print(f"Recursive search found {len(sbp_dirs)} directories with .spb files in '{root_dir}' and subdirectories.")

    return sbp_dirs


def write_correction_log(
    dir_correction_local,
    sbp_dirname,
    rtk_conf_name,
    correction_mode,
    ftp_host,
    ftp_remote_dir,
    files_used,
    files_downloaded,
    files_deleted,
):
    """
    Write correction data provenance log.
    """

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath_log = os.path.join(
        dir_correction_local, f"correction_data_log_{timestamp}.txt"
    )

    with open(filepath_log, "w") as f:
        f.write("RTK correction data log\n")
        f.write(f"Timestamp: {timestamp}\n\n")

        f.write(f"SBP directory: {sbp_dirname}\n")
        f.write(f"RTK config file: {rtk_conf_name}\n\n")

        f.write(f"Correction mode: {correction_mode}\n\n")

        if ftp_host is not None:
            f.write("Correction data source:\n")
            f.write(f"  FTP server: {ftp_host}\n")
            f.write(f"  Remote folder: {ftp_remote_dir}\n\n")

        if files_downloaded:
            f.write("Downloaded correction files:\n")
            for fname in files_downloaded:
                f.write(f"  {fname}\n")
            f.write("\n")

        f.write("Correction files used for RTK:\n")
        for fname in files_used:
            f.write(f"  {fname}\n")
        f.write("\n")

        f.write("Deleted correction files:\n")
        if files_deleted:
            for fname in files_deleted:
                f.write(f"  {fname}\n")
        else:
            f.write("  none\n")


def parse_args():

    parser = argparse.ArgumentParser(
        prog=f"rtkprocessing",
        description=(f"Automatically walk a folder tree, find all directories containing .sbp files, "
                      "download correction data, perform RTK-GNSS correction and export to .pos.")
    )
    parser.add_argument("--dir", required = True, type=str, help="Root directory. All directories containing .sbp below this directory will be processed.")
    parser.add_argument("--ftphost", type=str, default="gnss1.tudelft.nl", help="FTP host to download correction data from. Must accept anonymous connections. The default is gnss1.tudelft.nl")
    parser.add_argument("--corrdir", type=str, help="Use a global correction data directory shared across all SBP directories; correction data is never deleted and --keepcorrectiondata is ignored.")
    parser.add_argument("--station", type=str, default="DELF00NLD", help="The base station to download data from. The default is the EWI-tower (DELF00NLD)")
    parser.add_argument("--connect", action="store_true", help="Suppress prompt asking for connection when downloading correction data.")
    parser.add_argument("--rtkconfig", type=str, default='{DIR}/*.conf', help="Specify the RTKLib config file. If not specified, each sbp data directory is searched for a *.conf file.")
    parser.add_argument("--keepcorrectiondata", action="store_true", help="Keep correction data after processing each SBP directory; only applies when --corrdir is not used.")

    return parser.parse_args()


def main():
    args = parse_args()
    sbp_directories = get_sbp_dirs(args.dir)

    if args.corrdir is None:
        corr_dir = None
    else:
        corr_dir = args.corrdir

    if args.rtkconfig=='{DIR}/*.conf':
        conf_file = None
    else:
        if not os.path.isfile(args.rtkconfig):
            raise FileNotFoundError(f"Can't find RTKLib config file at '{args.rtkconfig}'")
        conf_file = args.rtkconfig

    for sbp_dir in sbp_directories:
        process_sbp_files(sbp_dir, args.ftphost, args.station, corr_dir=corr_dir, conf_file=conf_file, suppress_download_prompt=args.connect, keep_correction_data=args.keepcorrectiondata)

if __name__ == "__main__":
    main()


