# timelapse-backtracing
Script to trace plant main roots in a sequence of images, for example in a timelapse setup. 
It uses traced roots in .rsml format to backtrace the images of earlier timepoints. 
Includes subfolders of the indicated directory.

When multiple .rsml files are present, the files are divided in sections. Starting with either the first image or the first image after an .rsml file up until the file with the corresponding .rsml file. 

Dependencies:
  scipy
  opencv-pyhton
  numpy 
  BeautifulSoup
  re
  xml
  shutil
  
Use:
  1) Write the directory at line 8 and run the script.
  2) .rsml files are written for every image
