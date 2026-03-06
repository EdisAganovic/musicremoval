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
            public UInt32 ActiveProcessLimit;
            public UIntPtr Affinity;
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
                File.AppendAllText(logPath, string.Format("[{0}] [SpawnWithJob] {1}{2}", timestamp, message, Environment.NewLine));
            }
            catch (Exception ex)
            {
                // Last ditch effort to stderr if log file fails
                Console.Error.WriteLine("[SpawnWithJob] Failed to log to file: " + ex.Message);
            }
        }

        static int Main(string[] args)
        {
            try
            {
                if (args.Length == 0)
                {
                    Console.WriteLine("Usage: SpawnWithJob.exe <command> [args...]");
                    return 1;
                }

                string command = args[0];
                string arguments = args.Length > 1 ? string.Join(" ", EscapeArguments(args, 1)) : "";

                IntPtr hJob = CreateJobObject(IntPtr.Zero, null);
                if (hJob == IntPtr.Zero)
                {
                    int errCode = Marshal.GetLastWin32Error();
                    string err = string.Format("Failed to create job object. Error: {0}", errCode);
                    Log(err);
                    throw new Win32Exception(errCode);
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
                        int errCode = Marshal.GetLastWin32Error();
                        string err = string.Format("Failed to set job object information. Error: {0}", errCode);
                        Log(err);
                        throw new Win32Exception(errCode);
                    }
                }
                finally
                {
                    Marshal.FreeHGlobal(extendedInfoPtr);
                }

                ProcessStartInfo startInfo = new ProcessStartInfo(command, arguments)
                {
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    RedirectStandardInput = true
                };

                using (Process childProcess = new Process())
                {
                    childProcess.StartInfo = startInfo;
                    
                    // Set up event handlers for output and error
                    childProcess.OutputDataReceived += (sender, e) => { if (e.Data != null) Console.WriteLine(e.Data); };
                    childProcess.ErrorDataReceived += (sender, e) => { if (e.Data != null) Console.Error.WriteLine(e.Data); };

                    if (!childProcess.Start())
                    {
                        Log(string.Format("Failed to start process: {0} {1}", command, arguments));
                        Console.Error.WriteLine("Failed to start process.");
                        return 1;
                    }

                    if (!AssignProcessToJobObject(hJob, childProcess.Handle))
                    {
                        int errCode = Marshal.GetLastWin32Error();
                        Log(string.Format("Warning: Failed to assign process {0} to job object. Error: {1}", childProcess.Id, errCode));
                    }

                    // Start asynchronous reading
                    childProcess.BeginOutputReadLine();
                    childProcess.BeginErrorReadLine();

                    childProcess.WaitForExit();
                    
                    if (childProcess.ExitCode != 0)
                    {
                        Log(string.Format("Process exited with non-zero code {0}: {1} {2}", childProcess.ExitCode, command, arguments));
                    }
                    
                    return childProcess.ExitCode;
                }
            }
            catch (Exception ex)
            {
                string msg = string.Format("Fatal error: {0}{1}{2}", ex.Message, Environment.NewLine, ex.StackTrace);
                Log(msg);
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
                // Simple escaping for arguments with spaces
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

