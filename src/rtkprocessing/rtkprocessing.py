
import os
import sys
import glob
import subprocess
import tempfile

import pandas as pd
import numpy as np
import argparse
import matplotlib.pyplot as plt

from datetime import datetime, timedelta

from ftplib import FTP
import gzip
import shutil
import warnings

def get_timespans(out_dir, report_subdir='report', solution_subdir='solution'):
    """ Extract the timespan of each sbp file form the corresponding report. Requires that sbp2report has run already."""

    timespans = []
    sbp_filenames = [os.path.splitext(f)[0] for f in os.listdir() if f.endswith(".sbp")]
    pattern = r"%Y-%m-%d %H:%M:%S.%f"

    for fname in sbp_filenames:
        fpath_report = os.path.join(out_dir, report_subdir, fname, fname+'.csv')
        if not os.path.isfile(fpath_report):
            raise FileNotFoundError(f"Report file {fpath_report} does not exist!")
        
        fpath_pos = os.path.join(out_dir, solution_subdir, fname+'.pos')
        if os.path.isfile(fpath_pos):
            continue

        data = pd.read_csv(fpath_report)
        
        has_data =  data['UTC Time'].notna().any() and data['UTC Date'].notna().any()

        if has_data:
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


def get_correction_filenames(out_dir, **kwargs):
    """ Get all ftp filepaths of required to """

    timespans = get_timespans(out_dir)

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

def _apply_rtk_corrections(sbp_dir, out_dir, sbp_files, corr_dir, conf_file, host, suppress_download_prompt, station, SOLUTION_OUT, RINEX_OUT, REPORT_OUT):
    
    # Download correction data
    corr_filenames = get_correction_filenames(out_dir, station=station)
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
    
    data_files={}
    rtk_status=[]

    for sbp_file in sbp_files:
    
        fname_no_ext = os.path.splitext(sbp_file)[0]
        print(f"{fname_no_ext} ... ", end="")

        # Apply RTK corrections
        pos_file = os.path.join(out_dir, SOLUTION_OUT, f"{fname_no_ext}.pos")
        data_files[fname_no_ext] = (pos_file, os.path.join(out_dir, REPORT_OUT, fname_no_ext, f"{fname_no_ext}.csv"))
        if os.path.isfile(pos_file):
            print("Found existing .pos file. Skip!")
            rtk_status.append([fname_no_ext, "existed"])
            continue

        obs_file = os.path.join(out_dir, RINEX_OUT, f"{fname_no_ext}.obs")
        nav_file = os.path.join(out_dir, RINEX_OUT, f"{fname_no_ext}.nav")

        subprocess.run([
            "rnx2rtkp",
            "-k", conf_file,
            "-o", pos_file,
            obs_file,
            os.path.join(corr_dir, "*.crx"),
            nav_file
        ], shell=True, check=True)
        if os.path.isfile(pos_file):
            rtk_status.append([fname_no_ext, "created"])
        else:
            rtk_status.append([fname_no_ext, "failed "])
        print(f"output: {pos_file}, done!")

    rtk_status = pd.DataFrame(rtk_status, columns=["file", "rtk"])

    return data_files, rtk_status, files_downloaded, files_used, corr_filenames_missing, conf_file

def process_sbp_files(sbp_dir, out_dir, host, station, corr_dir=None, suppress_download_prompt=False, conf_file=None, keep_correction_data=False):
    print(f"Processing SBP files in {sbp_dir}:")

    # Define in-/output directories
    RINEX_OUT = "rinex"
    REPORT_OUT = "report"
    SOLUTION_OUT = "solution"
    CORR_OUT = "correction"

    cwd = os.getcwd()

    # Check if directory existed
    if not os.path.exists(sbp_dir):
        print(f"The given directory does not exist: {sbp_dir}")
        sys.exit(1)

    # Create output directories
    for folder in [RINEX_OUT, REPORT_OUT, SOLUTION_OUT]:
        os.makedirs(os.path.join(out_dir, folder), exist_ok=True)

    # Change to sbp_dir
    os.chdir(sbp_dir)

    # Process each .sbp file
    sbp_files = [f for f in os.listdir() if f.endswith(".sbp")]
    if len(sbp_files)==0:
        print("No .sbp files found in the directory.")
        sys.exit(1)

    logtable = []

    print("Extracting SBP files:")
    for sbp_file in sbp_files:
        fname_no_ext = os.path.splitext(sbp_file)[0]
        print(f"\n{fname_no_ext}\n----------")

        # Convert SBP to RINEX
        def exists_rinex():
            return  np.all([os.path.isfile(os.path.join(out_dir, RINEX_OUT, f"{fname_no_ext}{ftype}")) for ftype in [".nav", ".obs", ".sbs"]])
        if not exists_rinex():
            print("\nConverting SBP to RINEX ... ")
            subprocess.run(["sbp2rinex", os.path.join(sbp_dir, sbp_file), "-d", os.path.join(out_dir, RINEX_OUT)], check=True)
            print("done!")
            if exists_rinex():
                rinex_status = "created"
            else:
                rinex_status = "corrupt"
        else:
            print("\nFound existing RINEX ... ")
            rinex_status = "existed"

        # Generate report
        existed = [os.path.isfile(os.path.join(out_dir, REPORT_OUT, fname_no_ext, f"{fname_no_ext}{ftype}")) for ftype in [".csv", "-ins.csv", "-msg.csv", "-trk.csv"]]
        if not np.all(existed):
            print("\nGenerating report ... ")
            os.chdir(os.path.join(out_dir, REPORT_OUT))
            subprocess.run(["sbp2report", "-d", os.path.join(sbp_dir, sbp_file)], check=True)
            os.chdir(sbp_dir)
            print("done!")
            report_status = "created"
        else:
            print("\nFound existing report ... ")
            report_status = "existed"
        
        logtable.append([fname_no_ext, rinex_status, report_status])
    logtable = pd.DataFrame(logtable, columns=['file', 'rinex', 'report']) 

    # Apply rtk corrections
    if corr_dir is None:
        local_correction_data = True
        if keep_correction_data:
            corr_dir = os.path.join(out_dir, CORR_OUT)
            os.makedirs(corr_dir, exist_ok=True)
            data_files, rtk_status, files_downloaded, files_used, corr_filenames_missing, conf_file = _apply_rtk_corrections(sbp_dir, out_dir, sbp_files, corr_dir, conf_file, host, suppress_download_prompt, station, SOLUTION_OUT, RINEX_OUT, REPORT_OUT)
        else:
            with tempfile.TemporaryDirectory(prefix="rtkprocessing_") as corr_dir:
                data_files, rtk_status, files_downloaded, files_used, corr_filenames_missing, conf_file = _apply_rtk_corrections(sbp_dir, out_dir, sbp_files, corr_dir, conf_file, host, suppress_download_prompt, station, SOLUTION_OUT, RINEX_OUT, REPORT_OUT)
    else:
        if not os.path.exists(corr_dir):
            print(f"Couldn't find the specified correction data directory: {corr_dir}!")
            sys.exit(1)
        local_correction_data = False
        data_files, rtk_status, files_downloaded, files_used, corr_filenames_missing, conf_file = _apply_rtk_corrections(sbp_dir, out_dir, sbp_files, corr_dir, conf_file, host, suppress_download_prompt, station, SOLUTION_OUT, RINEX_OUT, REPORT_OUT)
    logtable = logtable.merge(rtk_status, on="file")

    # plotting   
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if len(data_files) > 0 and (logtable['rtk']=='created').any():
        fig = plot_processing_result(data_files)
        fig_file = os.path.join(out_dir, f"{timestamp}_rtkprocessing_results.png")
        fig.savefig(fig_file)
        plt.close(fig)
    
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

    processed = not (logtable[['rinex', 'report', 'rtk']]=="existed").all().all() 
    if processed:
        write_correction_log(
            timestamp,
            dir_correction_local=out_dir,
            sbp_dirname=os.path.basename(sbp_dir),
            rtk_conf_name=os.path.basename(conf_file),
            processing_log_table=logtable,
            correction_mode="automatic download" if local_correction_data else "user-defined correction data",
            ftp_host=host if files_downloaded else None,
            ftp_remote_dir=", ".join(remote_folders) if remote_folders else None,
            files_used=files_used,
            files_downloaded=files_downloaded,
            files_deleted=files_deleted,
        )

    # Return to original directory
    os.chdir(cwd)
    print(f"Finished! Results are in {os.path.join(out_dir, SOLUTION_OUT)}")


def get_sbp_dirs(root_dir):
    sbp_dirs = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Check if any file in this directory ends with .sbp
        if any(fname.lower().endswith(".sbp") for fname in filenames):
            sbp_dirs.append(dirpath)

    print(f"Recursive search found {len(sbp_dirs)} directories with .spb files in '{root_dir}' and subdirectories.")

    return sbp_dirs


def plot_processing_result(data_files):

    filekeys = list(data_files.keys())
    filekeys.sort()

    fig, ax = plt.subplots(1,1)
    ax.set_xlabel("Longitude [deg]")
    ax.set_ylabel("Latitude [deg]")
    ax.xaxis.set_major_formatter("{x:.6f}")
    ax.yaxis.set_major_formatter("{x:.6f}")

    ax.set_title(f"RTK Processing Results {filekeys[0]}-{filekeys[-1]}")

    #draw raw data
    nodes = []
    col_raw = '#C4C4C4'
    lat_mean = None
    for f in filekeys:
        if os.path.isfile(data_files[f][1]):
            data_report = pd.read_csv(data_files[f][1])
            if len(data_report) > 0:
                lat = data_report['Lat [deg]']
                lon = data_report['Lon [deg]']
                line_raw, = ax.plot(lon, lat, linestyle='dashed', color=col_raw)
                if not (lat.isna() & lat.isna()).all():
                    i = max(lon.first_valid_index(), lat.first_valid_index())
                    nodes.append((lon.iloc[i], lat.iloc[i]))
                    lat_mean = np.deg2rad(np.mean(lat))
    if len(data_report) > 0:
        nodes.append((lon.iloc[-1], lat.iloc[-1]))
    if len(nodes) > 0:
        nodes = np.array(nodes)
        ax.scatter(nodes[:,0], nodes[:,1], c=col_raw, marker='s')

    if lat_mean is not None:
        ax.set_aspect(1.0 / np.cos(lat_mean))

    #draw processed data
    nodes_pos = []
    col_pos = '#00A6D6'
    for f in filekeys:
        if os.path.isfile(data_files[f][0]):
            data_pos = pd.read_table(data_files[f][0], sep=r"\s+", skiprows=23)
            if len(data_pos) > 0:
                lat = data_pos['latitude(deg)']
                lon = data_pos['longitude(deg)']
                line_pos, =ax.plot(lon, lat, color=col_pos)
                nodes_pos.append((lon.iloc[0], lat.iloc[0]))
    if len(data_pos) > 0:
        nodes_pos.append((lon.iloc[-1], lat.iloc[-1]))
    if len(nodes_pos) > 0:
        nodes_pos = np.array(nodes_pos)
        ax.scatter(nodes_pos[:,0], nodes_pos[:,1], c=col_pos, marker='s')

    if len(nodes) > 0 and len(nodes_pos) > 0:
        ax.legend(handles=[line_raw, line_pos], labels=["raw", "processed"])
    
    fig.set_size_inches(10,10)

    return fig


def write_correction_log(
    timestamp, 
    dir_correction_local,
    sbp_dirname,
    rtk_conf_name,
    processing_log_table,
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

    filepath_log = os.path.join(
        dir_correction_local, f"{timestamp}_rtkprocessing_log.txt"
    )

    with open(filepath_log, "w") as f:
        f.write("RTK correction data log\n")
        f.write(f"Timestamp: {timestamp}\n\n")

        f.write(f"SBP directory: {sbp_dirname}\n")
        f.write(f"RTK config file: {rtk_conf_name}\n\n")

        f.write(f"Correction data source: {correction_mode}\n\n")

        if ftp_host is not None:
            f.write("Correction data source:\n")
            f.write(f"  FTP server: {ftp_host}\n")
            f.write(f"  Remote folder: {ftp_remote_dir}\n\n")

        if files_downloaded:
            f.write("Downloaded correction files:\n")
            if files_downloaded:
                for fname in files_downloaded:
                    f.write(f"  {fname}\n")
            else:
                f.write("  none\n")
            f.write("\n")

        f.write("Correction files used for RTK:\n")
        if files_used:
            for fname in files_used:
                f.write(f"  {fname}\n")
        else:
            f.write("  none\n")
        f.write("\n")

        f.write("Deleted correction files:\n")
        if files_deleted:
            for fname in files_deleted:
                f.write(f"  {fname}\n")
        else:
            f.write("  none\n")
        f.write("\n")

        f.write("Processing Log:\n")
        f.write(processing_log_table.to_string(index=False))


def parse_args():

    parser = argparse.ArgumentParser(
        prog=f"rtkprocessing",
        description=(f"Automatically walk a folder tree, find all directories containing .sbp files, "
                      "download correction data, perform RTK-GNSS correction and export to .pos.")
    )
    parser.add_argument("--dir", required = True, type=str, help="Root directory. All directories containing .sbp below this directory will be processed.")
    parser.add_argument("--outdir", type=str, help="Root directory of the output. If given, the subfolder structure of the root directory is repeated in the output directory and results are stored in the corresponding subfolders. If not specified, the output is stored in the root directory.")
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
        rel_path = os.path.relpath(sbp_dir, start=args.dir)
        
        if args.outdir is None:
            out_dir = sbp_dir
        else:
            out_dir = os.path.join(args.outdir, rel_path)
        process_sbp_files(sbp_dir, out_dir, args.ftphost, args.station, corr_dir=corr_dir, conf_file=conf_file, suppress_download_prompt=args.connect, keep_correction_data=args.keepcorrectiondata)

if __name__ == "__main__":
    main()


