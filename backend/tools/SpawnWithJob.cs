using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.ComponentModel;
using System.IO;

namespace ProcessWrapper
{
    class Program
    {
        // Using explicit layout to ensure x64 alignment (SIZE_T/UIntPtr needs 8-byte alignment)
        [StructLayout(LayoutKind.Explicit)]
        struct JOBOBJECT_BASIC_LIMIT_INFORMATION
        {
            [FieldOffset(0)] public Int64 PerProcessUserTimeLimit;
            [FieldOffset(8)] public Int64 PerJobUserTimeLimit;
            [FieldOffset(16)] public UInt32 LimitFlags;
            [FieldOffset(24)] public UIntPtr MinimumWorkingSetSize;
            [FieldOffset(32)] public UIntPtr MaximumWorkingSetSize;
            [FieldOffset(40)] public UInt32 ActiveProcessLimit;
            [FieldOffset(48)] public UIntPtr Affinity;
            [FieldOffset(56)] public UInt32 PriorityClass;
            [FieldOffset(60)] public UInt32 SchedulingClass;
        }

        enum JobObjectInfoClass
        {
            BasicLimitInformation = 2
        }

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern IntPtr CreateJobObject(IntPtr lpJobAttributes, string lpName);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool SetInformationJobObject(IntPtr hJob, JobObjectInfoClass JobObjectInfoClass, IntPtr lpJobObjectInfo, uint cbJobObjectInfoLength);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool AssignProcessToJobObject(IntPtr hJob, IntPtr hProcess);

        const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000;

        static void Log(string message)
        {
            try
            {
                string exeDir = AppDomain.CurrentDomain.BaseDirectory;
                string rootDir = Path.GetFullPath(Path.Combine(exeDir, "..", ".."));
                string logPath = Path.Combine(rootDir, "log.txt");
                string timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
                File.AppendAllText(logPath, string.Format("[{0}] [SpawnWithJob] {1}{2}", timestamp, message, Environment.NewLine));
            }
            catch (Exception) { }
        }

        static int Main(string[] args)
        {
            try
            {
                if (args.Length == 0) return 0;

                string command = args[0];
                string arguments = args.Length > 1 ? string.Join(" ", EscapeArguments(args, 1)) : "";

                IntPtr hJob = CreateJobObject(IntPtr.Zero, null);
                if (hJob == IntPtr.Zero)
                {
                    Log("Failed to create job object.");
                    return 1;
                }

                var info = new JOBOBJECT_BASIC_LIMIT_INFORMATION();
                info.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;

                int length = Marshal.SizeOf(typeof(JOBOBJECT_BASIC_LIMIT_INFORMATION));
                IntPtr infoPtr = Marshal.AllocHGlobal(length);
                try
                {
                    Marshal.StructureToPtr(info, infoPtr, false);
                    if (!SetInformationJobObject(hJob, JobObjectInfoClass.BasicLimitInformation, infoPtr, (uint)length))
                    {
                        int errCode = Marshal.GetLastWin32Error();
                        Log(string.Format("Failed to set job limits. Error: {0}. Continuing anyway...", errCode));
                    }
                }
                finally { Marshal.FreeHGlobal(infoPtr); }

                ProcessStartInfo startInfo = new ProcessStartInfo(command, arguments)
                {
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    RedirectStandardInput = true
                };

                using (Process proc = new Process())
                {
                    proc.StartInfo = startInfo;
                    proc.OutputDataReceived += (s, e) => { if (e.Data != null) Console.WriteLine(e.Data); };
                    proc.ErrorDataReceived += (s, e) => { if (e.Data != null) Console.Error.WriteLine(e.Data); };

                    if (!proc.Start()) return 1;
                    AssignProcessToJobObject(hJob, proc.Handle);

                    proc.BeginOutputReadLine();
                    proc.BeginErrorReadLine();
                    proc.WaitForExit();
                    return proc.ExitCode;
                }
            }
            catch (Exception ex)
            {
                Log("Fatal: " + ex.Message);
                return 1;
            }
        }

        static string[] EscapeArguments(string[] args, int start)
        {
            string[] escaped = new string[args.Length - start];
            for (int i = start; i < args.Length; i++)
            {
                string arg = args[i];
                if (arg.Contains(" ") || arg.Contains("\""))
                    escaped[i - start] = "\"" + arg.Replace("\"", "\\\"") + "\"";
                else
                    escaped[i - start] = arg;
            }
            return escaped;
        }
    }
}
