# `spreadsheets` folder

This is where the spreadsheets belong:

1. `DAL_ABCD_merged_pcqcinfo.csv` (the DAIC QC info)
1. `image03.txt` (the NDA DICOM imaging data info)
1. `ABCD_good_bad_series_table.csv` (generated after `data_gatherer` is run)

The `DAL_ABCD_merged_pcqcinfo.csv` is currently only available from the ABCD DAIC. So, it is only accessible for someone within the ABCD consortium (who can access ABCD data on the NDA website). However, the MRI QC scores will soon be uploaded to NDA. Afterwards, this script will be updated to download that file and read from it instead of requiring the user to manually get the `DAL_ABCD_merged_pcqcinfo.csv` spreadsheet.