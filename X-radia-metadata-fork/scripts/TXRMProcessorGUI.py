import os
from XradiaPy import Data
import json
from datetime import datetime
import logging
from Tkinter import *
import tkFileDialog
import ttk
import threading

class TXRMProcessorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("TXRM Metadata Extractor")
        self.root.geometry("800x600")
        
        # Initialize file list and output directory
        self.files_to_process = []
        self.output_dir = os.path.join(os.getcwd(), "metadata_output")
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
        # Setup logging
        self.setup_logging()
        
        # Create GUI elements
        self.create_gui()
        
        # Initialize processor
        self.processor = MetadataProcessor(self.output_dir)
        
    def setup_logging(self):
        log_file = os.path.join(self.output_dir, 
                               'txrm_processing_{0}.log'.format(
                                   datetime.now().strftime("%Y%m%d_%H%M%S")))
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def create_gui(self):
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(N, W, E, S))
        
        # File selection buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=0, column=0, columnspan=2, pady=5)
        
        ttk.Button(btn_frame, text="Select Files", 
                  command=self.select_files).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="Select Folder", 
                  command=self.select_folder).grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text="Clear List", 
                  command=self.clear_files).grid(row=0, column=2, padx=5)
        
        # File list
        list_frame = ttk.LabelFrame(main_frame, text="Files to Process", padding="5")
        list_frame.grid(row=1, column=0, columnspan=2, sticky=(N, W, E, S), pady=5)
        
        self.file_listbox = Listbox(list_frame, width=80, height=15)
        self.file_listbox.grid(row=0, column=0, sticky=(N, W, E, S))
        
        # Scrollbar for file list
        scrollbar = ttk.Scrollbar(list_frame, orient=VERTICAL, 
                                command=self.file_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky=(N, S))
        self.file_listbox.configure(yscrollcommand=scrollbar.set)
        
        # Progress information
        self.progress_var = StringVar(value="Ready to process files...")
        ttk.Label(main_frame, textvariable=self.progress_var).grid(
            row=2, column=0, columnspan=2, pady=5)
        
        self.progress_bar = ttk.Progressbar(main_frame, length=300, mode='determinate')
        self.progress_bar.grid(row=3, column=0, columnspan=2, pady=5)
        
        # Process button
        self.process_btn = ttk.Button(main_frame, text="Process Files", 
                                    command=self.start_processing)
        self.process_btn.grid(row=4, column=0, columnspan=2, pady=10)
        
        # Output text
        output_frame = ttk.LabelFrame(main_frame, text="Processing Output", padding="5")
        output_frame.grid(row=5, column=0, columnspan=2, sticky=(N, W, E, S), pady=5)
        
        self.output_text = Text(output_frame, width=80, height=10, wrap=WORD)
        self.output_text.grid(row=0, column=0, sticky=(N, W, E, S))
        
        # Scrollbar for output
        output_scrollbar = ttk.Scrollbar(output_frame, orient=VERTICAL, 
                                       command=self.output_text.yview)
        output_scrollbar.grid(row=0, column=1, sticky=(N, S))
        self.output_text.configure(yscrollcommand=output_scrollbar.set)

    def select_files(self):
        files = tkFileDialog.askopenfilenames(
            title="Select TXRM files",
            filetypes=[("TXRM files", "*.txrm"), ("All files", "*.*")]
        )
        if files:
            self.add_files(files)

    def select_folder(self):
        folder = tkFileDialog.askdirectory(title="Select Folder")
        if folder:
            for root, _, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith('.txrm'):
                        self.add_files([os.path.join(root, file)])

    def add_files(self, files):
        for file in files:
            if file not in self.files_to_process:
                self.files_to_process.append(file)
                self.file_listbox.insert(END, file)
        self.update_progress("Added {0} files. Total: {1}".format(
            len(files), len(self.files_to_process)))

    def clear_files(self):
        self.files_to_process = []
        self.file_listbox.delete(0, END)
        self.update_progress("File list cleared")

    def update_progress(self, message):
        self.progress_var.set(message)
        self.root.update_idletasks()

    def append_output(self, message):
        self.output_text.insert(END, message + "\n")
        self.output_text.see(END)
        self.root.update_idletasks()

    def start_processing(self):
        if not self.files_to_process:
            self.update_progress("No files to process!")
            return
            
        self.process_btn.state(['disabled'])
        self.progress_bar['maximum'] = len(self.files_to_process)
        self.progress_bar['value'] = 0
        
        # Start processing in a separate thread
        threading.Thread(target=self.process_files).start()

    def process_files(self):
        for i, file_path in enumerate(self.files_to_process, 1):
            try:
                self.update_progress("Processing file {0} of {1}...".format(
                    i, len(self.files_to_process)))
                
                metadata = self.processor.get_metadata(file_path)
                if metadata:
                    output_path = self.processor.save_metadata(metadata, file_path)
                    self.append_output("Processed: {0}".format(os.path.basename(file_path)))
                    self.append_output("Output: {0}".format(output_path))
                else:
                    self.append_output("Failed to process: {0}".format(file_path))
                
                self.progress_bar['value'] = i
                
            except Exception as e:
                self.logger.error("Error processing {0}: {1}".format(file_path, str(e)))
                self.append_output("Error processing {0}: {1}".format(file_path, str(e)))
        
        self.update_progress("Processing complete!")
        self.process_btn.state(['!disabled'])

class MetadataProcessor:
    def __init__(self, output_dir):
        self.dataset = Data.XRMData.XrmBasicDataSet()
        self.output_dir = output_dir

    def get_metadata(self, file_path):
        try:
            self.dataset.ReadFile(file_path)
            
            num_projections = self.dataset.GetProjections()
            axes = self.dataset.GetAxesNames()
            
            return {
                "file_info": {
                    "file_path": file_path,
                    "file_name": self.dataset.GetName(),
                    "acquisition_complete": self.dataset.IsInitializedCorrectly()
                },
                "machine_settings": {
                    "objective": self.dataset.GetObjective(),
                    "pixel_size_um": self.dataset.GetPixelSize(),
                    "power_watts": self.dataset.GetPower(),
                    "voltage_kv": self.dataset.GetVoltage(),
                    "filter": self.dataset.GetFilter(),
                    "binning": self.dataset.GetBinning()
                },
                "image_properties": {
                    "height_pixels": self.dataset.GetHeight(),
                    "width_pixels": self.dataset.GetWidth(),
                    "total_projections": num_projections
                },
                "projection_summary": self._get_projection_summary(num_projections, axes)
            }
        except Exception as e:
            logging.error("Error processing file {0}: {1}".format(file_path, str(e)))
            return None

    def _get_projection_summary(self, num_projections, axes):
        if num_projections == 0:
            return {}
            
        summary = {
            "projection_count": num_projections,
            "time_span": {
                "start_date": self.dataset.GetDate(0),
                "end_date": self.dataset.GetDate(num_projections - 1)
            }
        }
        
        return summary

    def save_metadata(self, metadata, file_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = os.path.splitext(os.path.basename(file_path))[0]
        output_path = os.path.join(
            self.output_dir, 
            "{0}_metadata_{1}.json".format(base_filename, timestamp)
        )
        
        with open(output_path, 'w') as f:
            json.dump(metadata, f, indent=4, sort_keys=True)
        
        return output_path

def main():
    root = Tk()
    app = TXRMProcessorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
