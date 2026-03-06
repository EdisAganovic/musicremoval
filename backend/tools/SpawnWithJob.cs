using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.ComponentModel;
using System.IO;

namespace ProcessWrapper
{
    class Program
    {
        [StructLayout(LayoutKind.Sequential)]
        struct JOBOBJECT_BASIC_LIMIT_INFORMATION
        {
            public Int64 PerProcessUserTimeLimit;
            public Int64 PerJobUserTimeLimit;
            public UInt32 LimitFlags;
            public UIntPtr MinimumWorkingSetSize;
            public UIntPtr MaximumWorkingSetSize;
            public UIntPtr Affinitiy;
            public UInt32 ActiveProcessLimit;
            public UIntPtr AffinitiyValue;
            public UInt32 PriorityClass;
            public UInt32 SchedulingClass;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct IO_COUNTERS
        {
            public UInt64 ReadOperationCount;
            public UInt64 WriteOperationCount;
            public UInt64 OtherOperationCount;
            public UInt64 ReadTransferCount;
            public UInt64 WriteTransferCount;
            public UInt64 OtherTransferCount;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
        {
            public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
            public IO_COUNTERS IoInfo;
            public UIntPtr ProcessMemoryLimit;
            public UIntPtr JobMemoryLimit;
            public UIntPtr PeakProcessMemoryLimit;
            public UIntPtr PeakJobMemoryLimit;
        }

        enum JobObjectInfoClass
        {
            ExtendedLimitInformation = 9
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
                File.AppendAllText(logPath, $"[{timestamp}] [SpawnWithJob] {message}" + Environment.NewLine);
            }
            catch { }
        }

        static int Main(string[] args)
        {
            if (args.Length == 0)
            {
                Console.WriteLine("Usage: SpawnWithJob.exe <command> [args...]");
                return 1;
            }

            string command = args[0];
            string fullLine = string.Join(" ", args);

            IntPtr hJob = CreateJobObject(IntPtr.Zero, null);
            if (hJob == IntPtr.Zero)
            {
                string err = $"Failed to create job object. Error: {Marshal.GetLastWin32Error()}";
                Log(err);
                throw new Win32Exception(Marshal.GetLastWin32Error());
            }

            var info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;

            int length = Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
            IntPtr extendedInfoPtr = Marshal.AllocHGlobal(length);
            try
            {
                Marshal.StructureToPtr(info, extendedInfoPtr, false);
                if (!SetInformationJobObject(hJob, JobObjectInfoClass.ExtendedLimitInformation, extendedInfoPtr, (uint)length))
                {
                    string err = $"Failed to set job object information. Error: {Marshal.GetLastWin32Error()}";
                    Log(err);
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                }
            }
            finally
            {
                Marshal.FreeHGlobal(extendedInfoPtr);
            }

            string arguments = args.Length > 1 ? string.Join(" ", EscapeArguments(args, 1)) : "";

            ProcessStartInfo startInfo = new ProcessStartInfo(command, arguments)
            {
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                RedirectStandardInput = true
            };

            try
            {
                Process childProcess = new Process();
                childProcess.StartInfo = startInfo;
                
                // Set up event handlers for output and error
                childProcess.OutputDataReceived += (sender, e) => { if (e.Data != null) Console.WriteLine(e.Data); };
                childProcess.ErrorDataReceived += (sender, e) => { if (e.Data != null) Console.Error.WriteLine(e.Data); };

                if (!childProcess.Start())
                {
                    Log($"Failed to start process: {command} {arguments}");
                    Console.Error.WriteLine("Failed to start process.");
                    return 1;
                }

                if (!AssignProcessToJobObject(hJob, childProcess.Handle))
                {
                    // This might fail if the process already exited or other reasons
                    // Log it as a warning
                    Log($"Warning: Failed to assign process {childProcess.Id} to job object. Error: {Marshal.GetLastWin32Error()}");
                }

                // Start asynchronous reading
                childProcess.BeginOutputReadLine();
                childProcess.BeginErrorReadLine();

                childProcess.WaitForExit();
                
                if (childProcess.ExitCode != 0)
                {
                    Log($"Process exited with non-zero code {childProcess.ExitCode}: {command} {arguments}");
                }
                
                return childProcess.ExitCode;
            }
            catch (Exception ex)
            {
                Log($"Exception while running {command}: {ex.Message}{Environment.NewLine}{ex.StackTrace}");
                Console.Error.WriteLine("Error: " + ex.Message);
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
                {
                    escaped[i - start] = "\"" + arg.Replace("\"", "\\\"") + "\"";
                }
                else
                {
                    escaped[i - start] = arg;
                }
            }
            return escaped;
        }
    }
}

