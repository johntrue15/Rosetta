- Need a small windowed application to run in background and scan a list
  of directories for new files every 5 minutes.
- Directory scanning should be recursive, descending into subdirectories to find .txrm files.
- Python 3.10 or higher should be used for this application.
- Files to be scanned end in .txrm. When a new file is found, the app should add it to
  a list of files that is checked every 10 minutes for changes in file
  size. If the file size changes, the timer restarts for that file.
- When a file has not changed in size for 10 minutes, the app should process
  the file using the logic in get-metadata-from-txrm.py to get the metadata.
- Metadata output should be saved in a text file with the same name as the 
  .txrm file but with a .txt extension, in the same directory as the .txrm file. The output file will be named filename.txrm.txt.
- Files that have an existing associated .txrm.txt file do not need to be monitored.
- Failure to extract metadata is also noted by writing a filename.txrm.txt file
  and placing "ERROR PROCESSING METADATA" in the contents of the file, in
  addition to logging the failure.
- Files that encounter errors during processing should no longer be monitored for changes.
- The app should log its activity to a log file, including when it starts,
  when it finds new files, when it processes files, and any errors that occur.
- Log files should go in a "logs" directory in the same location as the application.
- Log files should be rotated daily, with a new log file created each day.
- The application should have a simple GUI that shows the list of .txrm files
  being monitored, their current status (e.g., "Waiting for changes", 
  "Processing", "Completed"), and any errors that have occurred.
- Users should be able to select a file from the monitored files list and force
  immediate processing without waiting for the stability timer. This is useful
  for debugging and testing.
- The GUI should also have a running text window that shows the log output in real-time.
- A status bar at the bottom of the window should display which directories and/or files
  are currently being scanned or processed.
- The list of directories to monitor should be configurable in the GUI and saved in
  a local preferences file, ideally in JSON format.
- Errors in extracting metadata should be logged.
- The program should start manually, not on boot. It does not need to be a
  system tray application.
- The window may be minimized and the application will continue to run. If the
  windows is closed (exit), it is the same as quitting the application.
- Use PySide for the GUI framework.
- There is no maximum number of files that can be monitored. There should be no
  more than several hundred files to watch, so this should not be an issue.


