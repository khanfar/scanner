import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import json
import os
import win32com.client
from datetime import datetime
from cryptography.fernet import Fernet
from base64 import b64encode
from hashlib import sha256

class SDRLauncherGUI:
    def __init__(self, root):
        self.root = root
        
        # Initialize translations first
        self.translations = {
            'ar': {
                'window_title': 'أنظمة خنفر',
                'frequency_control': 'التحكم بالتردد',
                'frequency_mhz': 'التردد (ميجاهرتز):',
                'set': 'تعيين',
                'scanner_controls': 'أدوات المسح',
                'load_list': 'تحميل القائمة',
                'save_list': 'حفظ القائمة',
                'add_current': 'إضافة التردد الحالي',
                'launch': 'تشغيل',
                'start_scan': 'بدء المسح (S)',
                'stop_scan': 'إيقاف المسح (S)',
                'ready': 'جاهز',
                'scanning': 'جاري المسح...',
                'frequency_set': 'تم تعيين التردد: {} ميجاهرتز',
                'launch_success': 'تم التشغيل بنجاح',
                'save_success': 'تم الحفظ بنجاح',
                'settings_loaded': 'تم تحميل الإعدادات',
                'invalid_frequency': 'تردد غير صالح',
                'launch_fmp_first': 'الرجاء تشغيل البرنامج أولاً',
                'settings': 'الإعدادات',
                'advanced': 'متقدم',
                'language': 'اللغة',
                'save_settings': 'حفظ الإعدادات',
                'main_controls': 'التحكم الرئيسي',
                'activation_title': 'تفعيل البرنامج',
                'activation_message': 'الرجاء إدخال رمز التفعيل:',
                'invalid_key': 'رمز التفعيل غير صالح',
                'activation_success': 'تم التفعيل بنجاح',
                'activate': 'تفعيل'
            },
            'en': {
                'window_title': 'Khanfar Scanner',
                'frequency_control': 'Frequency Control',
                'frequency_mhz': 'Frequency (MHz):',
                'set': 'Set',
                'scanner_controls': 'Scanner Controls',
                'load_list': 'Load List',
                'save_list': 'Save List',
                'add_current': 'Add Current',
                'launch': 'Launch',
                'start_scan': 'Start Scan (S)',
                'stop_scan': 'Stop Scan (S)',
                'ready': 'Ready',
                'scanning': 'Scanning...',
                'frequency_set': 'Frequency set to: {} MHz',
                'launch_success': 'Launch successful',
                'save_success': 'Save successful',
                'settings_loaded': 'Settings loaded',
                'invalid_frequency': 'Invalid frequency',
                'launch_fmp_first': 'Please launch FMP24 first',
                'settings': 'Settings',
                'advanced': 'Advanced',
                'language': 'Language',
                'save_settings': 'Save Settings',
                'main_controls': 'Main Controls',
                'activation_title': 'Software Activation',
                'activation_message': 'Please enter your activation key:',
                'invalid_key': 'Invalid activation key',
                'activation_success': 'Activation successful',
                'activate': 'Activate'
            }
        }
        
        # Initialize language
        self.current_language = tk.StringVar(value='ar')
        self.current_language.trace_add('write', self.on_language_change)
        
        # Add encryption key
        self.encryption_key = b'khanfar_secure_key_2024'  # 32 bytes key
        
        # Check activation before proceeding
        if not self.check_activation():
            self.show_activation_dialog()
            if not hasattr(self, 'activated') or not self.activated:
                self.root.destroy()
                return
        
        self.root.title(self.get_text('window_title'))
        
        # Initialize variables
        self.scanning = False
        self.current_entry = None
        self.fmp_process = None
        self.scan_frequencies = []
        
        # Style configuration
        self.style = ttk.Style()
        self.style.configure('TButton', padding=5)
        self.style.configure('TLabel', padding=3)
        self.style.configure('TFrame', padding=5)
        
        # Configuration variables
        self.input_device = tk.StringVar(value="1")
        self.output_device = tk.StringVar(value="2")
        self.ppm = tk.StringVar(value="23")
        self.rf_gain = tk.StringVar(value="32")
        self.frequency = tk.StringVar(value="423")
        
        # Validate entries
        self.input_device.trace_add("write", self.validate_input_device)
        self.output_device.trace_add("write", self.validate_output_device)
        self.ppm.trace_add("write", self.validate_ppm)
        self.rf_gain.trace_add("write", self.validate_rf_gain)
        self.frequency.trace_add("write", self.validate_frequency)
        
        self.role_config = tk.BooleanVar(value=True)
        self.muted = tk.BooleanVar(value=False)
        
        # Create status label first
        self.status_frame = ttk.Frame(self.root, relief='sunken', padding="2")
        self.status_frame.pack(side='bottom', fill='x')
        
        self.status_label = ttk.Label(self.status_frame, text=self.get_text('ready'))
        self.status_label.pack(side='left')
        
        self.datetime_label = ttk.Label(self.status_frame, text="")
        self.datetime_label.pack(side='right')
        self.update_datetime()
        
        # Create GUI elements
        self.create_gui()
        
        # Load saved settings
        self.load_settings()
        
        # Bind keyboard shortcuts
        self.root.bind('<s>', self.toggle_scan)
        self.root.bind('<S>', self.toggle_scan)
        self.root.bind('g', lambda e: self.adjust_gain(-1))   # Decrease gain
        self.root.bind('G', lambda e: self.adjust_gain(1))   # Increase gain
        self.root.bind('p', lambda e: self.adjust_ppm(-1))   # Decrease PPM
        self.root.bind('P', lambda e: self.adjust_ppm(1))    # Increase PPM
        
    def get_text(self, key, *args):
        """Get translated text"""
        text = self.translations[self.current_language.get()].get(key, key)
        if args:
            return text.format(*args)
        return text

    def on_language_change(self, *args):
        """Update GUI text when language changes"""
        # Update window title
        self.root.title(self.get_text('window_title'))
        
        # Update notebook tabs
        self.notebook.tab(0, text=self.get_text('main_controls'))
        self.notebook.tab(1, text=self.get_text('scanner_controls'))
        self.notebook.tab(2, text=self.get_text('settings'))
        self.notebook.tab(3, text=self.get_text('advanced'))
        
        # Update scan button text
        if self.scanning:
            self.scan_btn.config(text=self.get_text('stop_scan'))
        else:
            self.scan_btn.config(text=self.get_text('start_scan'))
        
        # Update all frame labels
        for widget in self.root.winfo_children():
            self.update_widget_text(widget)
            
        # Save settings when language changes
        self.save_settings()
            
    def update_widget_text(self, widget):
        """Recursively update text for all widgets"""
        try:
            if isinstance(widget, (ttk.Button, ttk.Label, ttk.LabelFrame)):
                current_text = widget.cget('text')
                # Find matching key by checking both English and Arabic values
                for lang in ['en', 'ar']:
                    for key, value in self.translations[lang].items():
                        if str(value) == str(current_text):
                            widget.configure(text=self.get_text(key))
                            break
                            
            # Update children widgets
            for child in widget.winfo_children():
                self.update_widget_text(child)
        except:
            pass  # Skip any widgets that can't be updated
            
    def create_gui(self):
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Create tabs
        main_frame = ttk.Frame(self.notebook)
        scanner_frame = ttk.Frame(self.notebook)
        settings_frame = ttk.Frame(self.notebook)
        advanced_frame = ttk.Frame(self.notebook)
        
        self.notebook.add(main_frame, text=self.get_text('main_controls'))
        self.notebook.add(scanner_frame, text=self.get_text('scanner_controls'))
        self.notebook.add(settings_frame, text=self.get_text('settings'))
        self.notebook.add(advanced_frame, text=self.get_text('advanced'))
        
        # Create controls in each tab
        self.create_main_controls(main_frame)
        self.create_scanner_controls(scanner_frame)
        self.create_settings_controls(settings_frame)
        self.create_advanced_controls(advanced_frame)

    def create_main_controls(self, parent):
        # Frequency control frame
        freq_frame = ttk.LabelFrame(parent, text=self.get_text('frequency_control'), padding="5")
        freq_frame.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
        
        ttk.Label(freq_frame, text=self.get_text('frequency_mhz')).grid(row=0, column=0, sticky='w', padx=5)
        freq_entry = ttk.Entry(freq_frame, textvariable=self.frequency, width=12)
        freq_entry.grid(row=0, column=1, padx=5)
        freq_entry.bind('<Return>', self.set_frequency)
        ttk.Button(freq_frame, text=self.get_text('set'), command=self.set_frequency).grid(row=0, column=2, padx=5)
        
        # Step size selector
        self.step_size = tk.StringVar(value="0.00625")  # 6.25 kHz
        ttk.Label(freq_frame, text="Step (MHz):").grid(row=1, column=0, sticky='w', padx=5)
        steps = ["0.00625", "0.0125", "0.025", "0.05", "0.1"]
        step_combo = ttk.Combobox(freq_frame, textvariable=self.step_size, values=steps, width=10)
        step_combo.grid(row=1, column=1, padx=5)
        
        # Device control frame
        device_frame = ttk.LabelFrame(parent, text="Device Control", padding="5")
        device_frame.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        
        ttk.Label(device_frame, text="Input Device:").grid(row=0, column=0, sticky='w', padx=5)
        ttk.Entry(device_frame, textvariable=self.input_device, width=10).grid(row=0, column=1, padx=5)
        
        ttk.Label(device_frame, text="Output Device:").grid(row=1, column=0, sticky='w', padx=5)
        ttk.Entry(device_frame, textvariable=self.output_device, width=10).grid(row=1, column=1, padx=5)
        
        # Control buttons frame
        control_frame = ttk.Frame(parent, padding="5")
        control_frame.grid(row=3, column=0, sticky='ew', pady=10)
        
        ttk.Button(control_frame, text=self.get_text('launch'), command=self.launch_fmp24).pack(side='left', padx=5)
        self.scan_btn = ttk.Button(control_frame, text=self.get_text('start_scan'), command=self.toggle_scan)
        self.scan_btn.pack(side='left', padx=5)
        ttk.Button(control_frame, text=self.get_text('save_settings'), command=self.save_config).pack(side='left', padx=5)
        
    def create_scanner_controls(self, parent):
        scanner_frame = ttk.LabelFrame(parent, text=self.get_text('scanner_controls'), padding="5")
        scanner_frame.pack(fill='both', expand=True, padx=5, pady=5)

        # Scan list using Text widget for direct editing
        list_frame = ttk.Frame(scanner_frame)
        list_frame.pack(fill='both', expand=True, padx=5, pady=5)

        self.scan_list = tk.Text(list_frame, height=10, width=30)
        self.scan_list.pack(side='left', fill='both', expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.scan_list.yview)
        scrollbar.pack(side='right', fill='y')
        self.scan_list.config(yscrollcommand=scrollbar.set)

        # Button frame
        btn_frame = ttk.Frame(scanner_frame)
        btn_frame.pack(fill='x', pady=5)
        
        ttk.Button(btn_frame, text=self.get_text('load_list'), command=self.load_scan_list).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=self.get_text('save_list'), command=self.save_scan_list).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=self.get_text('add_current'), command=self.add_frequency).pack(side='left', padx=5)

        # Load initial scan list
        self.load_scan_list()

    def create_settings_controls(self, parent):
        # Settings frame
        settings_frame = ttk.LabelFrame(parent, text=self.get_text('settings'), padding="5")
        settings_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # PPM correction
        ttk.Label(settings_frame, text="PPM Correction:").grid(row=0, column=0, sticky='w', padx=5)
        ppm_frame = ttk.Frame(settings_frame)
        ppm_frame.grid(row=0, column=1, sticky='w', padx=5)
        
        ttk.Label(ppm_frame, text="Use 'p' to decrease, 'P' to increase").pack(side='left', padx=5)
        ttk.Button(ppm_frame, text="P↑", command=lambda: self.adjust_ppm(1)).pack(side='left', padx=2)
        ttk.Button(ppm_frame, text="p↓", command=lambda: self.adjust_ppm(-1)).pack(side='left', padx=2)
        
        # RF Gain
        ttk.Label(settings_frame, text="RF Gain Control:").grid(row=1, column=0, sticky='w', padx=5)
        gain_frame = ttk.Frame(settings_frame)
        gain_frame.grid(row=1, column=1, sticky='w', padx=5)
        
        ttk.Label(gain_frame, text="Use 'g' to decrease, 'G' to increase").pack(side='left', padx=5)
        ttk.Button(gain_frame, text="G↑", command=lambda: self.adjust_gain(1)).pack(side='left', padx=2)
        ttk.Button(gain_frame, text="g↓", command=lambda: self.adjust_gain(-1)).pack(side='left', padx=2)
        
        # Role configuration
        ttk.Checkbutton(settings_frame, text="Role Configuration (-rc)",
                      variable=self.role_config).grid(row=2, column=0, columnspan=2, sticky='w', padx=5)
        
        # Batch file controls
        batch_frame = ttk.LabelFrame(settings_frame, text="Batch File", padding="5")
        batch_frame.grid(row=3, column=0, columnspan=2, sticky='ew', padx=5, pady=10)
        
        ttk.Button(batch_frame, text="Create Batch File", command=self.create_batch).pack(side='left', padx=5)
        ttk.Button(batch_frame, text="Load Defaults", command=self.load_defaults).pack(side='left', padx=5)
        
    def create_advanced_controls(self, parent):
        """Create advanced settings controls"""
        advanced_frame = ttk.LabelFrame(parent, text=self.get_text('advanced'), padding="5")
        advanced_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Language selection
        lang_frame = ttk.LabelFrame(advanced_frame, text=self.get_text('language'), padding="5")
        lang_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Radiobutton(lang_frame, text="عربي", value="ar", 
                       variable=self.current_language).pack(side='left', padx=20)
        ttk.Radiobutton(lang_frame, text="English", value="en",
                       variable=self.current_language).pack(side='left', padx=20)

    def update_datetime(self):
        """Update the datetime display in the status bar"""
        self.datetime_label.config(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.root.after(1000, self.update_datetime)
        
    def step_frequency(self, direction):
        """Step the frequency up or down by the selected step size"""
        try:
            current = float(self.frequency.get())
            step = float(self.step_size.get())
            new_freq = current + (direction * step)
            self.frequency.set(f"{new_freq:.6f}")
            if self.fmp_process:
                self.send_command(f"f{new_freq}")
        except ValueError:
            self.status_label.config(text="Invalid frequency or step size")
            
    def update_volume(self, *args):
        """Update the volume level"""
        if self.fmp_process:
            self.send_command(f"v100")  # Set default volume
            
    def toggle_mute(self, event=None):
        """Toggle mute state"""
        if self.fmp_process:
            self.muted.set(not self.muted.get())
            if self.muted.get():
                self.send_command("m1")
                self.status_label.config(text="Audio muted")
            else:
                self.send_command("m0")
                self.status_label.config(text="Audio unmuted")
            
    def send_command(self, cmd):
        """Send a command to FMP24 window"""
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.AppActivate("FMP24")
            shell.SendKeys(cmd)
        except Exception as e:
            self.status_label.config(text=f"Command failed: {str(e)}")
            
    def load_scan_list(self):
        """Load frequencies from FMP24.ScanList"""
        try:
            with open("FMP24.ScanList", 'r') as file:
                content = file.read()
                self.scan_list.delete('1.0', tk.END)
                self.scan_list.insert('1.0', content)
                self.status_label.config(text="Loaded FMP24.ScanList")
        except Exception as e:
            self.status_label.config(text=f"Could not load FMP24.ScanList: {str(e)}")

    def save_scan_list(self):
        """Save current scan list to FMP24.ScanList"""
        was_scanning = self.scanning  # Remember if we were scanning
        
        if was_scanning:
            # Stop scanning with Esc key
            self.scanning = False
            if self.fmp_process:
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.AppActivate("FMP24")
                # Send Esc to stop scanning
                shell.SendKeys("{ESC}")
        
        try:
            content = self.scan_list.get('1.0', tk.END)
            with open("FMP24.ScanList", 'w') as file:
                file.write(content)
            self.status_label.config(text="Saved to FMP24.ScanList")
            
            if was_scanning:
                # Wait a moment before restarting scan
                self.root.after(2000, self.restart_scan)
                
        except Exception as e:
            self.status_label.config(text=f"Could not save FMP24.ScanList: {str(e)}")
            
    def restart_scan(self):
        """Restart scanning after save"""
        if self.fmp_process:
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.AppActivate("FMP24")
            shell.SendKeys("s")  # Press 'S' to restart scanning
            self.scanning = True
            self.status_label.config(text="Scanning restarted")
            
    def add_frequency(self):
        """Add current frequency to scan list"""
        try:
            freq = float(self.frequency.get())
            self.scan_list.insert(tk.END, f"{freq:.3f} NFM\n")
            self.save_scan_list()  # Auto-save after adding
            self.status_label.config(text=f"Added frequency: {freq:.3f} MHz")
        except ValueError:
            messagebox.showerror("Error", "Invalid frequency value")

    def toggle_scan(self, event=None):
        """Toggle scanning mode"""
        try:
            if not self.scanning:
                # Get frequencies from Text widget and parse them
                frequencies = []
                for line in self.scan_list.get('1.0', tk.END).splitlines():
                    if line.strip():  # Skip empty lines
                        # Split line and take first part as frequency
                        freq_str = line.split()[0]  # Take first part before NFM
                        try:
                            freq = float(freq_str)
                            frequencies.append(freq)
                        except ValueError:
                            continue  # Skip invalid frequencies
                            
                if not frequencies:
                    messagebox.showwarning("Warning", "No valid frequencies in scan list")
                    return
                    
                self.scan_frequencies = frequencies
                self.scanning = True
                
                # Send scan command to FMP24
                if self.fmp_process:
                    shell = win32com.client.Dispatch("WScript.Shell")
                    shell.AppActivate("FMP24")
                    shell.SendKeys("s")
                    self.status_label.config(text="Scanning started")
                else:
                    messagebox.showwarning("Warning", "Please launch FMP24 first")
                    self.scanning = False
            else:
                # Stop scanning with Esc key
                self.scanning = False
                if self.fmp_process:
                    shell = win32com.client.Dispatch("WScript.Shell")
                    shell.AppActivate("FMP24")
                    # Send Esc to stop scanning
                    shell.SendKeys("{ESC}")
                self.status_label.config(text="Scanning stopped")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to toggle scanning: {str(e)}")
            self.scanning = False
            
    def adjust_gain(self, direction):
        """Adjust gain using g/G keys"""
        try:
            current_gain = float(self.rf_gain.get())
            new_gain = current_gain + (1 * direction)
            self.rf_gain.set(f"{new_gain:.1f}")
            if self.fmp_process:
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.AppActivate("FMP24")
                if direction > 0:
                    shell.SendKeys("G")
                else:
                    shell.SendKeys("g")
                self.status_label.config(text=f"RF Gain: {new_gain:.1f}")
                # Save settings after adjustment
                self.save_settings()
        except Exception as e:
            self.status_label.config(text=f"Failed to adjust gain: {str(e)}")
                
    def adjust_ppm(self, direction):
        """Adjust PPM using p/P keys"""
        try:
            current_ppm = float(self.ppm.get())
            new_ppm = current_ppm + (0.1 * direction)
            self.ppm.set(f"{new_ppm:.1f}")
            if self.fmp_process:
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.AppActivate("FMP24")
                if direction > 0:
                    shell.SendKeys("P")
                else:
                    shell.SendKeys("p")
                self.status_label.config(text=f"PPM correction: {new_ppm:.1f}")
                # Save settings after adjustment
                self.save_settings()
        except Exception as e:
            self.status_label.config(text=f"Failed to adjust PPM: {str(e)}")
                
    def validate_input_device(self, *args):
        try:
            value = int(self.input_device.get())
            if not (1 <= value <= 255):
                self.status_label.config(text="Input device must be between 1 and 255")
                return False
        except ValueError:
            self.status_label.config(text="Input device must be a number")
            return False
        return True
        
    def validate_ppm(self, *args):
        try:
            value = float(self.ppm.get())
            if not (-999.9 <= value <= 999.9):
                self.status_label.config(text="PPM must be between -999.9 and 999.9")
                return False
        except ValueError:
            self.status_label.config(text="PPM must be a number")
            return False
        return True
        
    def validate_frequency(self, *args):
        try:
            value = float(self.frequency.get())
            if value <= 0:
                self.status_label.config(text="Frequency must be positive")
                return False
        except ValueError:
            self.status_label.config(text="Frequency must be a number")
            return False
        return True
        
    def validate_rf_gain(self, *args):
        try:
            value = int(self.rf_gain.get())
            if not (0 <= value <= 50):
                self.status_label.config(text="RF Gain must be between 0 and 50")
                return False
        except ValueError:
            self.status_label.config(text="RF Gain must be a number")
            return False
        return True
        
    def validate_output_device(self, *args):
        try:
            value = int(self.output_device.get())
            if not (1 <= value <= 255):
                self.status_label.config(text="Output device must be between 1 and 255")
                return False
        except ValueError:
            self.status_label.config(text="Output device must be a number")
            return False
        return True
        
    def create_batch(self):
        try:
            cmd = f'FMP24 {"-rc " if self.role_config.get() else ""}-i{self.input_device.get()} -P{self.ppm.get()} -f{self.frequency.get()} -g{self.rf_gain.get()} -o{self.output_device.get()}'
            with open('FMP24-CUSTOM.bat', 'w') as f:
                f.write(cmd)
            self.status_label.config(text="Batch file created: FMP24-CUSTOM.bat")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create batch file: {str(e)}")
            
    def launch_fmp24(self):
        try:
            cmd = ["FMP24"]
            
            if self.role_config.get():
                cmd.append("-rc")
                
            cmd.extend([
                f"-i{self.input_device.get()}",
                f"-P{self.ppm.get()}",
                f"-f{self.frequency.get()}",
                f"-g{self.rf_gain.get()}",
                f"-o{self.output_device.get()}"
            ])
            
            cmd.append("-_3")  # Minimize both windows
            
            # Launch FMP24
            self.fmp_process = subprocess.Popen(cmd)
            self.status_label.config(text="FMP24 launched successfully")
            
            # Save current configuration
            self.save_config()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch FMP24: {str(e)}")
            self.status_label.config(text="Launch failed")
    
    def save_config(self):
        config = {
            'input_device': self.input_device.get(),
            'ppm': self.ppm.get(),
            'frequency': self.frequency.get(),
            'rf_gain': self.rf_gain.get(),
            'output_device': self.output_device.get(),
            'role_config': self.role_config.get()
        }
        
        try:
            with open("launcher_config.json", 'w') as f:
                json.dump(config, f, indent=4)
            self.status_label.config(text="Configuration saved")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")
    
    def load_config(self):
        try:
            if os.path.exists("launcher_config.json"):
                with open("launcher_config.json", 'r') as f:
                    config = json.load(f)
                    
                self.input_device.set(config.get('input_device', '1'))
                self.ppm.set(config.get('ppm', '23'))
                self.frequency.set(config.get('frequency', '423'))
                self.rf_gain.set(config.get('rf_gain', '32'))
                self.output_device.set(config.get('output_device', '2'))
                self.role_config.set(config.get('role_config', True))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load configuration: {str(e)}")
    
    def load_defaults(self):
        self.input_device.set("1")
        self.ppm.set("23")
        self.frequency.set("423")
        self.rf_gain.set("32")
        self.output_device.set("2")
        self.role_config.set(True)
        self.status_label.config(text="Default settings loaded")
        
    def save_settings(self):
        """Save current settings to file"""
        settings = {
            'ppm': self.ppm.get(),
            'gain': self.rf_gain.get(),
            'input_device': self.input_device.get(),
            'output_device': self.output_device.get(),
            'language': self.current_language.get()  # Save language preference
        }
        try:
            with open("fmp_settings.json", 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            self.status_label.config(text=f"Could not save settings: {str(e)}")

    def load_settings(self):
        """Load settings from file"""
        try:
            if os.path.exists("fmp_settings.json"):
                with open("fmp_settings.json", 'r') as f:
                    settings = json.load(f)
                self.ppm.set(settings.get('ppm', '0'))
                self.rf_gain.set(settings.get('gain', '50'))
                self.input_device.set(settings.get('input_device', '1'))
                self.output_device.set(settings.get('output_device', '1'))
                
                # Load and set language preference
                saved_language = settings.get('language', 'ar')
                self.current_language.set(saved_language)
                
                self.status_label.config(text="Settings loaded")
        except Exception as e:
            # Set defaults if loading fails
            self.ppm.set('0')
            self.rf_gain.set('50')
            self.input_device.set('1')
            self.output_device.set('1')
            self.current_language.set('ar')  # Default to Arabic
            self.status_label.config(text=f"Could not load settings: {str(e)}")
            
    def set_frequency(self, event=None):
        """Set frequency directly in FMP24"""
        try:
            freq = float(self.frequency.get())
            if self.fmp_process:
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.AppActivate("FMP24")
                
                # If scanning, stop it first with Esc
                if self.scanning:
                    shell.SendKeys("{ESC}")
                    self.scanning = False
                    self.root.after(200)  # Wait for scan to stop
                
                # Type each digit with delay
                freq_str = f"{freq:.3f}"
                for digit in freq_str:
                    shell.SendKeys(digit)
                    self.root.after(200)  # 200ms delay between digits
                
                # Press Enter
                shell.SendKeys("{ENTER}")
                self.status_label.config(text=self.get_text('frequency_set').format(freq))
            else:
                messagebox.showwarning("Warning", self.get_text('launch_fmp_first'))
        except ValueError:
            messagebox.showerror("Error", self.get_text('invalid_frequency'))

    def check_activation(self):
        """Check if software is activated"""
        documents_path = os.path.expanduser('~/Documents')
        license_file = os.path.join(documents_path, '.khanfar_license')
        
        if os.path.exists(license_file):
            try:
                with open(license_file, 'r') as f:
                    encrypted_key = f.read().strip()
                # Decrypt and validate the key
                decrypted_key = self.decrypt_key(encrypted_key)
                return self.validate_key(decrypted_key)
            except:
                return False
        return False
    
    def validate_key(self, key):
        """Validate the activation key"""
        # For this example, we'll accept key "1234567890"
        return key == "1234567890"
    
    def encrypt_key(self, key):
        """Encrypt the activation key"""
        fernet_key = b64encode(sha256(self.encryption_key).digest())
        f = Fernet(fernet_key)
        
        # Encrypt the key
        return f.encrypt(key.encode()).decode()
    
    def decrypt_key(self, encrypted_key):
        """Decrypt the activation key"""
        try:
            fernet_key = b64encode(sha256(self.encryption_key).digest())
            f = Fernet(fernet_key)
            
            # Decrypt the key
            return f.decrypt(encrypted_key.encode()).decode()
        except:
            return ""
    
    def save_activation(self, key):
        """Save the activation key"""
        documents_path = os.path.expanduser('~/Documents')
        license_file = os.path.join(documents_path, '.khanfar_license')
        
        try:
            # Encrypt the key before saving
            encrypted_key = self.encrypt_key(key)
            with open(license_file, 'w') as f:
                f.write(encrypted_key)
            return True
        except:
            return False
    
    def show_activation_dialog(self):
        """Show activation dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title(self.get_text('activation_title'))
        dialog.geometry('400x250')  # Made dialog bigger
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry(f'{width}x{height}+{x}+{y}')
        
        # Create main frame with padding
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill='both', expand=True)
        
        # Message with bigger font
        message_label = ttk.Label(main_frame, 
                                text=self.get_text('activation_message'),
                                wraplength=350,
                                font=('Arial', 12))
        message_label.pack(pady=20)
        
        # Entry frame
        entry_frame = ttk.Frame(main_frame)
        entry_frame.pack(fill='x', pady=20)
        
        # Entry for key with bigger size
        key_var = tk.StringVar()
        key_entry = ttk.Entry(entry_frame, 
                            textvariable=key_var, 
                            width=35,
                            font=('Arial', 11))
        key_entry.pack(pady=5)
        key_entry.focus()
        
        def validate():
            key = key_var.get().strip()
            if self.validate_key(key):
                if self.save_activation(key):
                    self.activated = True
                    messagebox.showinfo("Success", self.get_text('activation_success'))
                    dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to save activation key")
            else:
                messagebox.showerror("Error", self.get_text('invalid_key'))
        
        # Activate button with bigger size
        ttk.Button(main_frame, 
                  text=self.get_text('activate'),
                  command=validate,
                  style='Big.TButton').pack(pady=20)
        
        # Create bigger button style
        style = ttk.Style()
        style.configure('Big.TButton', font=('Arial', 11))
        
        # Handle dialog close
        def on_close():
            self.activated = False
            dialog.destroy()
        
        dialog.protocol("WM_DELETE_WINDOW", on_close)
        
        # Wait for dialog to close
        dialog.wait_window()
        
if __name__ == "__main__":
    root = tk.Tk()
    app = SDRLauncherGUI(root)
    root.mainloop()
