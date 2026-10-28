using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace TaoYongStudioInstaller
{
    static class Program
    {
        [DllImport("user32.dll")]
        private static extern bool SetProcessDPIAware();

        [STAThread]
        static void Main(string[] args)
        {
            try { SetProcessDPIAware(); } catch { }
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            bool silent = false;
            string targetDir = null;

            foreach (var arg in args)
            {
                if (arg.Equals("/silent", StringComparison.OrdinalIgnoreCase) || arg.Equals("/s", StringComparison.OrdinalIgnoreCase))
                {
                    silent = true;
                }
                else if (arg.StartsWith("/dir=", StringComparison.OrdinalIgnoreCase))
                {
                    targetDir = arg.Substring(5).Trim('"', '\'');
                }
            }

            if (silent)
            {
                RunSilentInstall(targetDir);
                return;
            }

            Application.Run(new MainForm(targetDir));
        }

        static void RunSilentInstall(string targetDir)
        {
            if (string.IsNullOrEmpty(targetDir))
            {
                targetDir = MainForm.GetDefaultInstallDir();
            }

            try
            {
                MainForm.ExtractFiles(targetDir, null, null);
                MainForm.SetupFoldersAndConfig(targetDir, null);
                MainForm.RunSetupBat(targetDir, null);
                MainForm.CreateDesktopShortcut(targetDir, null);
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("Install failed: " + ex.Message);
                Environment.Exit(1);
            }
        }
    }

    public class MainForm : Form
    {
        private TextBox txtTargetDir;
        private Button btnBrowse;
        private CheckBox chkDesktopShortcut;
        private CheckBox chkRunSetup;
        private CheckBox chkStartApp;
        private ProgressBar progressBar;
        private Label lblStatus;
        private TextBox txtLog;
        private Button btnInstall;
        private Button btnCancel;
        private Thread workerThread;
        private bool isFinished = false;

        public MainForm(string initialDir)
        {
            InitializeComponent();
            if (!string.IsNullOrEmpty(initialDir))
            {
                txtTargetDir.Text = initialDir;
            }
            else
            {
                txtTargetDir.Text = GetDefaultInstallDir();
            }
        }

        public static string GetDefaultInstallDir()
        {
            try
            {
                string testPath = @"C:\TaoYongStudio";
                if (Directory.Exists(testPath)) return testPath;
                string testFile = @"C:\__taoyong_perm_test.tmp";
                using (var fs = File.Create(testFile)) { }
                File.Delete(testFile);
                return @"C:\TaoYongStudio";
            }
            catch
            {
                return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "TaoYongStudio");
            }
        }

        private void InitializeComponent()
        {
            this.Text = "TaoYongStudio Installer - ตัวติดตั้งโปรแกรม";
            this.Size = new Size(650, 610);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.StartPosition = FormStartPosition.CenterScreen;
            this.Font = new Font("Segoe UI", 9F, FontStyle.Regular, GraphicsUnit.Point);
            this.BackColor = Color.FromArgb(248, 250, 252);

            try
            {
                using (var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("AppIcon"))
                {
                    if (stream != null)
                    {
                        this.Icon = new Icon(stream);
                    }
                }
            }
            catch { }

            // Top Header Panel
            Panel pnlHeader = new Panel
            {
                Location = new Point(0, 0),
                Size = new Size(650, 75),
                BackColor = Color.FromArgb(30, 27, 75),
                Dock = DockStyle.Top
            };

            PictureBox picLogo = new PictureBox
            {
                Location = new Point(18, 12),
                Size = new Size(50, 50),
                SizeMode = PictureBoxSizeMode.Zoom
            };
            try
            {
                if (this.Icon != null) picLogo.Image = this.Icon.ToBitmap();
            }
            catch { }

            Label lblTitle = new Label
            {
                Text = "TaoYongStudio (เต่ายงสตูดิโอ)",
                Location = new Point(78, 13),
                AutoSize = true,
                Font = new Font("Segoe UI", 13.5F, FontStyle.Bold, GraphicsUnit.Point),
                ForeColor = Color.White
            };

            Label lblSubtitle = new Label
            {
                Text = "ระบบสร้างการ์ตูนแอนิเมชันเด็กภาษาไทยอัตโนมัติ (TikTok / YouTube)",
                Location = new Point(80, 42),
                AutoSize = true,
                Font = new Font("Segoe UI", 8.8F, FontStyle.Regular, GraphicsUnit.Point),
                ForeColor = Color.FromArgb(199, 210, 254)
            };

            pnlHeader.Controls.Add(picLogo);
            pnlHeader.Controls.Add(lblTitle);
            pnlHeader.Controls.Add(lblSubtitle);
            this.Controls.Add(pnlHeader);

            // GroupBox Destination
            GroupBox grpDest = new GroupBox
            {
                Text = "โฟลเดอร์สำหรับติดตั้ง (Destination Folder)",
                Location = new Point(18, 86),
                Size = new Size(598, 68),
                ForeColor = Color.FromArgb(15, 23, 42)
            };

            txtTargetDir = new TextBox
            {
                Location = new Point(14, 26),
                Size = new Size(470, 25),
                Font = new Font("Segoe UI", 9.5F, FontStyle.Regular, GraphicsUnit.Point)
            };

            btnBrowse = new Button
            {
                Text = "เรียกดู...",
                Location = new Point(492, 24),
                Size = new Size(92, 28),
                BackColor = Color.FromArgb(241, 245, 249),
                UseVisualStyleBackColor = true
            };
            btnBrowse.Click += BtnBrowse_Click;

            grpDest.Controls.Add(txtTargetDir);
            grpDest.Controls.Add(btnBrowse);
            this.Controls.Add(grpDest);

            // GroupBox Options
            GroupBox grpOpt = new GroupBox
            {
                Text = "ตัวเลือกเพิ่มเติม (Options)",
                Location = new Point(18, 160),
                Size = new Size(598, 92),
                ForeColor = Color.FromArgb(15, 23, 42)
            };

            chkDesktopShortcut = new CheckBox
            {
                Text = "สร้างทางลัดบนหน้าจอเดสก์ท็อป (TaoYongStudio Desktop Shortcut)",
                Location = new Point(16, 20),
                Size = new Size(550, 20),
                Checked = true
            };

            chkRunSetup = new CheckBox
            {
                Text = "เตรียม Virtual Environment (.venv) และติดตั้งแพ็กเกจ Python ทันที (แนะนำ)",
                Location = new Point(16, 42),
                Size = new Size(550, 20),
                Checked = true
            };

            chkStartApp = new CheckBox
            {
                Text = "เปิดโปรแกรม TaoYongStudio ทันทีหลังจากติดตั้งเสร็จสิ้น",
                Location = new Point(16, 64),
                Size = new Size(550, 20),
                Checked = true
            };

            grpOpt.Controls.Add(chkDesktopShortcut);
            grpOpt.Controls.Add(chkRunSetup);
            grpOpt.Controls.Add(chkStartApp);
            this.Controls.Add(grpOpt);

            // GroupBox Progress & Log
            GroupBox grpProgress = new GroupBox
            {
                Text = "ความคืบหน้าการติดตั้ง (Installation Progress)",
                Location = new Point(18, 258),
                Size = new Size(598, 240),
                ForeColor = Color.FromArgb(15, 23, 42)
            };

            lblStatus = new Label
            {
                Text = "สถานะ: พร้อมทำการติดตั้ง",
                Location = new Point(14, 20),
                Size = new Size(570, 18),
                Font = new Font("Segoe UI", 9F, FontStyle.Bold, GraphicsUnit.Point),
                ForeColor = Color.FromArgb(71, 85, 105)
            };

            progressBar = new ProgressBar
            {
                Location = new Point(14, 40),
                Size = new Size(570, 20),
                Minimum = 0,
                Maximum = 100,
                Value = 0
            };

            txtLog = new TextBox
            {
                Location = new Point(14, 68),
                Size = new Size(570, 160),
                Multiline = true,
                ReadOnly = true,
                ScrollBars = ScrollBars.Vertical,
                BackColor = Color.FromArgb(15, 23, 42),
                ForeColor = Color.FromArgb(226, 232, 240),
                Font = new Font("Consolas", 8.5F, FontStyle.Regular, GraphicsUnit.Point)
            };

            grpProgress.Controls.Add(lblStatus);
            grpProgress.Controls.Add(progressBar);
            grpProgress.Controls.Add(txtLog);
            this.Controls.Add(grpProgress);

            // Bottom Buttons
            btnInstall = new Button
            {
                Text = "เริ่มติดตั้ง",
                Location = new Point(374, 514),
                Size = new Size(125, 36),
                BackColor = Color.FromArgb(91, 63, 224),
                ForeColor = Color.White,
                FlatStyle = FlatStyle.Flat,
                Font = new Font("Segoe UI", 9.5F, FontStyle.Bold, GraphicsUnit.Point),
                Cursor = Cursors.Hand
            };
            btnInstall.FlatAppearance.BorderSize = 0;
            btnInstall.Click += BtnInstall_Click;

            btnCancel = new Button
            {
                Text = "ยกเลิก",
                Location = new Point(507, 514),
                Size = new Size(109, 36),
                BackColor = Color.FromArgb(226, 232, 240),
                ForeColor = Color.FromArgb(30, 41, 59),
                FlatStyle = FlatStyle.Flat,
                Font = new Font("Segoe UI", 9F, FontStyle.Regular, GraphicsUnit.Point)
            };
            btnCancel.FlatAppearance.BorderSize = 0;
            btnCancel.Click += BtnCancel_Click;

            this.Controls.Add(btnInstall);
            this.Controls.Add(btnCancel);

            this.FormClosing += MainForm_FormClosing;
        }

        private void BtnBrowse_Click(object sender, EventArgs e)
        {
            using (FolderBrowserDialog fbd = new FolderBrowserDialog())
            {
                fbd.Description = "เลือกโฟลเดอร์สำหรับติดตั้ง TaoYongStudio:";
                fbd.SelectedPath = txtTargetDir.Text;
                if (fbd.ShowDialog(this) == DialogResult.OK)
                {
                    txtTargetDir.Text = fbd.SelectedPath;
                }
            }
        }

        private void BtnCancel_Click(object sender, EventArgs e)
        {
            if (isFinished)
            {
                this.Close();
                return;
            }

            if (workerThread != null && workerThread.IsAlive)
            {
                if (MessageBox.Show("กระบวนการติดตั้งกำลังทำงานอยู่ คุณต้องการยกเลิกและปิดหรือไม่?", "ยืนยันการยกเลิก", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) == DialogResult.Yes)
                {
                    try { workerThread.Abort(); } catch { }
                    this.Close();
                }
            }
            else
            {
                this.Close();
            }
        }

        private void MainForm_FormClosing(object sender, FormClosingEventArgs e)
        {
            if (!isFinished && workerThread != null && workerThread.IsAlive)
            {
                try { workerThread.Abort(); } catch { }
            }
        }

        private void AppendLog(string message)
        {
            if (txtLog.InvokeRequired)
            {
                txtLog.BeginInvoke(new Action<string>(AppendLog), message);
                return;
            }
            string time = DateTime.Now.ToString("HH:mm:ss");
            txtLog.AppendText("[" + time + "] " + message + Environment.NewLine);
            txtLog.SelectionStart = txtLog.TextLength;
            txtLog.ScrollToCaret();
        }

        private void UpdateProgress(int percent, string statusText)
        {
            if (this.InvokeRequired)
            {
                this.BeginInvoke(new Action<int, string>(UpdateProgress), percent, statusText);
                return;
            }
            if (percent >= 0 && percent <= 100) progressBar.Value = percent;
            if (!string.IsNullOrEmpty(statusText)) lblStatus.Text = "สถานะ: " + statusText;
        }

        private void BtnInstall_Click(object sender, EventArgs e)
        {
            if (isFinished)
            {
                if (chkStartApp.Checked)
                {
                    LaunchApp(txtTargetDir.Text);
                }
                this.Close();
                return;
            }

            string targetDir = txtTargetDir.Text.Trim();
            if (string.IsNullOrEmpty(targetDir))
            {
                MessageBox.Show("กรุณาระบุโฟลเดอร์สำหรับติดตั้ง", "ข้อผิดพลาด", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            btnInstall.Enabled = false;
            btnBrowse.Enabled = false;
            txtTargetDir.ReadOnly = true;
            chkDesktopShortcut.Enabled = false;
            chkRunSetup.Enabled = false;
            chkStartApp.Enabled = false;
            btnCancel.Text = "ปิด";

            bool doShortcut = chkDesktopShortcut.Checked;
            bool doSetup = chkRunSetup.Checked;

            workerThread = new Thread(() =>
            {
                try
                {
                    AppendLog("=== เริ่มต้นกระบวนการติดตั้ง TaoYongStudio ===");
                    AppendLog("โฟลเดอร์ปลายทาง: " + targetDir);

                    // 1. Extract files
                    UpdateProgress(10, "กำลังแตกไฟล์โปรแกรม...");
                    AppendLog("[1/4] กำลังแตกไฟล์โปรแกรม...");
                    ExtractFiles(targetDir, AppendLog, (p) => UpdateProgress(10 + (int)(p * 0.45), "กำลังแตกไฟล์... " + (int)(p * 100) + "%"));
                    AppendLog("แตกไฟล์โปรแกรมเรียบร้อยแล้ว");

                    // 2. Prepare folders & config
                    UpdateProgress(60, "เตรียมโฟลเดอร์และไฟล์คอนฟิก...");
                    AppendLog("[2/4] เตรียมโครงสร้างโฟลเดอร์และ config.json...");
                    SetupFoldersAndConfig(targetDir, AppendLog);

                    // 3. Setup Python venv
                    if (doSetup)
                    {
                        UpdateProgress(65, "กำลังติดตั้ง Python venv และแพ็กเกจ (อาจใช้เวลา 2-5 นาที)...");
                        AppendLog("[3/4] เรียกใช้งาน setup.bat /yes เพื่อเตรียม Python environment...");
                        RunSetupBat(targetDir, AppendLog);
                    }
                    else
                    {
                        AppendLog("[3/4] ข้ามขั้นตอนสร้าง Python environment ตามที่เลือก");
                    }

                    // 4. Desktop Shortcut
                    if (doShortcut)
                    {
                        UpdateProgress(95, "กำลังสร้าง Desktop Shortcut...");
                        AppendLog("[4/4] กำลังสร้างทางลัดบนหน้าเดสก์ท็อป...");
                        CreateDesktopShortcut(targetDir, AppendLog);
                    }

                    UpdateProgress(100, "การติดตั้งเสร็จสมบูรณ์!");
                    AppendLog("==============================================");
                    AppendLog("  การติดตั้งเสร็จสมบูรณ์ พร้อมเปิดใช้งานได้ทันที!");
                    AppendLog("==============================================");

                    this.BeginInvoke(new Action(() =>
                    {
                        isFinished = true;
                        btnInstall.Text = chkStartApp.Checked ? "เปิดโปรแกรม" : "เสร็จสิ้น";
                        btnInstall.BackColor = Color.FromArgb(22, 163, 74);
                        btnInstall.Enabled = true;
                    }));
                }
                catch (ThreadAbortException)
                {
                    // cancelled
                }
                catch (Exception ex)
                {
                    AppendLog("เกิดข้อผิดพลาดในการติดตั้ง: " + ex.Message);
                    UpdateProgress(0, "การติดตั้งล้มเหลว");
                    this.BeginInvoke(new Action(() =>
                    {
                        btnInstall.Enabled = true;
                        btnInstall.Text = "ลองใหม่";
                        btnInstall.BackColor = Color.FromArgb(220, 38, 38);
                        btnBrowse.Enabled = true;
                        txtTargetDir.ReadOnly = false;
                        chkDesktopShortcut.Enabled = true;
                        chkRunSetup.Enabled = true;
                        chkStartApp.Enabled = true;
                        MessageBox.Show("การติดตั้งไม่สำเร็จ: " + ex.Message, "ข้อผิดพลาด", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    }));
                }
            });

            workerThread.IsBackground = true;
            workerThread.Start();
        }

        public static void ExtractFiles(string targetDir, Action<string> log, Action<double> progress)
        {
            if (!Directory.Exists(targetDir))
            {
                Directory.CreateDirectory(targetDir);
            }

            var asm = Assembly.GetExecutingAssembly();
            using (var stream = asm.GetManifestResourceStream("DataZip"))
            {
                if (stream == null)
                {
                    throw new FileNotFoundException("ไม่พบข้อมูล Resource ไฟล์สำหรับติดตั้งในไฟล์ exe");
                }

                using (var archive = new ZipArchive(stream, ZipArchiveMode.Read))
                {
                    int total = archive.Entries.Count;
                    int count = 0;

                    foreach (var entry in archive.Entries)
                    {
                        count++;
                        if (progress != null && total > 0)
                        {
                            progress((double)count / total);
                        }

                        if (string.IsNullOrEmpty(entry.Name) && (entry.FullName.EndsWith("/") || entry.FullName.EndsWith("\\")))
                        {
                            string dirPath = Path.Combine(targetDir, entry.FullName.TrimEnd('/', '\\'));
                            if (!Directory.Exists(dirPath)) Directory.CreateDirectory(dirPath);
                            continue;
                        }

                        string destPath = Path.Combine(targetDir, entry.FullName);
                        // Keep the user's edited/deleted ideas when installing an update.
                        string relativePath = entry.FullName.Replace('/', '\\');
                        if (relativePath.Equals(@"plans\ideas.json", StringComparison.OrdinalIgnoreCase)
                            && File.Exists(destPath))
                        {
                            continue;
                        }
                        string parentDir = Path.GetDirectoryName(destPath);
                        if (!string.IsNullOrEmpty(parentDir) && !Directory.Exists(parentDir))
                        {
                            Directory.CreateDirectory(parentDir);
                        }

                        entry.ExtractToFile(destPath, true);
                    }

                    if (log != null) log("แตกไฟล์ทั้งหมด " + total + " รายการสำเร็จ");
                }
            }
        }

        public static void SetupFoldersAndConfig(string targetDir, Action<string> log)
        {
            string[] subdirs = new string[] {
                @"scripts\inbox",
                @"scripts\done",
                @"scripts\failed",
                @"scripts\compilations",
                @"scripts\samples",
                @"output",
                @"logs",
                @"cache",
                @"secrets",
                @"plans\requests",
                @"plans\results"
            };

            foreach (var sd in subdirs)
            {
                string p = Path.Combine(targetDir, sd);
                if (!Directory.Exists(p)) Directory.CreateDirectory(p);
            }

            string cfgExample = Path.Combine(targetDir, "config.example.json");
            string cfgTarget = Path.Combine(targetDir, "config.json");
            if (File.Exists(cfgExample) && !File.Exists(cfgTarget))
            {
                File.Copy(cfgExample, cfgTarget);
                if (log != null) log("สร้าง config.json จาก config.example.json สำเร็จ");
            }
        }

        public static void RunSetupBat(string targetDir, Action<string> log)
        {
            string setupBat = Path.Combine(targetDir, "setup.bat");
            if (!File.Exists(setupBat))
            {
                if (log != null) log("ไม่พบ setup.bat ข้ามขั้นตอน");
                return;
            }

            var psi = new ProcessStartInfo
            {
                FileName = "cmd.exe",
                Arguments = "/c setup.bat /yes",
                WorkingDirectory = targetDir,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
                StandardOutputEncoding = Encoding.UTF8,
                StandardErrorEncoding = Encoding.UTF8
            };

            using (var proc = new Process())
            {
                proc.StartInfo = psi;
                proc.OutputDataReceived += (s, e) =>
                {
                    if (!string.IsNullOrEmpty(e.Data) && log != null) log(e.Data);
                };
                proc.ErrorDataReceived += (s, e) =>
                {
                    if (!string.IsNullOrEmpty(e.Data) && log != null) log("[STDERR] " + e.Data);
                };

                proc.Start();
                proc.BeginOutputReadLine();
                proc.BeginErrorReadLine();
                proc.WaitForExit();

                if (log != null) log("setup.bat เสร็จสิ้น (Exit Code: " + proc.ExitCode + ")");
            }
        }

        public static void CreateDesktopShortcut(string targetDir, Action<string> log)
        {
            string desktop = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
            string shortcutPath = Path.Combine(desktop, "TaoYongStudio.lnk");

            try
            {
                Type shellType = Type.GetTypeFromProgID("WScript.Shell");
                if (shellType != null)
                {
                    object shell = Activator.CreateInstance(shellType);
                    object shortcut = shellType.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { shortcutPath });
                    Type scType = shortcut.GetType();

                    string pythonw = Path.Combine(targetDir, @".venv\Scripts\pythonw.exe");
                    if (File.Exists(pythonw))
                    {
                        scType.InvokeMember("TargetPath", BindingFlags.SetProperty, null, shortcut, new object[] { pythonw });
                        scType.InvokeMember("Arguments", BindingFlags.SetProperty, null, shortcut, new object[] { "-m studio.gui" });
                    }
                    else
                    {
                        scType.InvokeMember("TargetPath", BindingFlags.SetProperty, null, shortcut, new object[] { Path.Combine(targetDir, "TaoYongStudio.bat") });
                        scType.InvokeMember("Arguments", BindingFlags.SetProperty, null, shortcut, new object[] { "" });
                    }

                    scType.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, shortcut, new object[] { targetDir });

                    string ico = Path.Combine(targetDir, @"studio\app.ico");
                    if (File.Exists(ico))
                    {
                        scType.InvokeMember("IconLocation", BindingFlags.SetProperty, null, shortcut, new object[] { ico + ",0" });
                    }

                    scType.InvokeMember("Description", BindingFlags.SetProperty, null, shortcut, new object[] { "TaoYongStudio - ระบบสร้างคลิปการ์ตูน" });
                    scType.InvokeMember("Save", BindingFlags.InvokeMethod, null, shortcut, null);

                    if (log != null) log("สร้างทางลัดบน Desktop สำเร็จ: " + shortcutPath);
                    return;
                }
            }
            catch (Exception ex)
            {
                if (log != null) log("สร้าง Shortcut ด้วย WScript.Shell ไม่สำเร็จ (" + ex.Message + ") กำลังลองด้วย PowerShell...");
            }

            // Fallback via PowerShell
            try
            {
                string makeShortcutBat = Path.Combine(targetDir, "make_shortcut.bat");
                if (File.Exists(makeShortcutBat))
                {
                    Process.Start(new ProcessStartInfo
                    {
                        FileName = "cmd.exe",
                        Arguments = "/c make_shortcut.bat",
                        WorkingDirectory = targetDir,
                        CreateNoWindow = true,
                        UseShellExecute = false
                    }).WaitForExit();
                }
            }
            catch { }
        }

        private static void LaunchApp(string targetDir)
        {
            try
            {
                string bat = Path.Combine(targetDir, "TaoYongStudio.bat");
                if (File.Exists(bat))
                {
                    Process.Start(new ProcessStartInfo
                    {
                        FileName = bat,
                        WorkingDirectory = targetDir,
                        UseShellExecute = true
                    });
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show("ไม่สามารถเปิดโปรแกรมได้: " + ex.Message, "ข้อผิดพลาด", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
        }
    }
}

