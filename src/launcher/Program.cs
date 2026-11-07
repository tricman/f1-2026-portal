using System;
using System.Diagnostics;
using System.IO;
using System.Text;

namespace F1Simulator
{
    class Program
    {
        static int Main(string[] args)
        {
            try
            {
                Console.OutputEncoding = Encoding.UTF8;
            }
            catch { }

            try
            {
                Console.Title = "F1 2026 Showrunner — Discord Listener";
            }
            catch { }

            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine("==================================================================");
            Console.WriteLine("   🏎️  F1 2026 SIMULATOR — DISCORD SHOWRUNNER LISTENER");
            Console.WriteLine("==================================================================");
            Console.ResetColor();

            // Locate project root directory (where orchestrator.md is)
            string baseDir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            if (!File.Exists(Path.Combine(baseDir, "orchestrator.md")))
            {
                DirectoryInfo parent = Directory.GetParent(baseDir);
                if (parent != null && File.Exists(Path.Combine(parent.FullName, "orchestrator.md")))
                {
                    baseDir = parent.FullName;
                }
            }

            Console.WriteLine(string.Format("[DIRETÓRIO] {0}", baseDir));

            // Locate Python executable
            string pythonExe = FindPythonExecutable();
            if (string.IsNullOrEmpty(pythonExe))
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("[ERRO] Python não foi encontrado no PATH nem nos diretórios padrão.");
                Console.ResetColor();
                Console.WriteLine("\nPressione qualquer tecla para sair...");
                Console.ReadKey();
                return 1;
            }

            Console.WriteLine(string.Format("[PYTHON]    {0}", pythonExe));
            Console.ForegroundColor = ConsoleColor.Green;
            Console.WriteLine("[STATUS]    Iniciando listener do Discord (#geral + DMs privadas)...");
            Console.WriteLine("[INFO]      Pressione Ctrl+C para encerrar com segurança.");
            Console.ResetColor();
            Console.WriteLine("==================================================================\n");

            // Build arguments
            StringBuilder cmdArgs = new StringBuilder("-m src.orchestrator_cli --action watch-discord");
            if (args != null && args.Length > 0)
            {
                foreach (string arg in args)
                {
                    if (arg.Contains(" "))
                    {
                        cmdArgs.Append(" \"").Append(arg).Append("\"");
                    }
                    else
                    {
                        cmdArgs.Append(" ").Append(arg);
                    }
                }
            }

            ProcessStartInfo psi = new ProcessStartInfo
            {
                FileName = pythonExe,
                Arguments = cmdArgs.ToString(),
                WorkingDirectory = baseDir,
                UseShellExecute = false,
                RedirectStandardInput = false,
                RedirectStandardOutput = false,
                RedirectStandardError = false,
                CreateNoWindow = false,
            };
            psi.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";

            try
            {
                using (Process proc = Process.Start(psi))
                {
                    if (proc == null)
                    {
                        Console.ForegroundColor = ConsoleColor.Red;
                        Console.WriteLine("[ERRO] Falha ao iniciar processo Python.");
                        Console.ResetColor();
                        Console.WriteLine("Pressione qualquer tecla para sair...");
                        Console.ReadKey();
                        return 1;
                    }

                    // Handle Ctrl+C
                    Console.CancelKeyPress += delegate(object sender, ConsoleCancelEventArgs e)
                    {
                        try
                        {
                            if (!proc.HasExited)
                            {
                                proc.Kill();
                            }
                        }
                        catch { }
                    };

                    proc.WaitForExit();
                    int exitCode = proc.ExitCode;

                    if (exitCode != 0)
                    {
                        Console.ForegroundColor = ConsoleColor.Yellow;
                        Console.WriteLine(string.Format("\n[AVISO] O processo encerrou com código de saída {0}.", exitCode));
                        Console.ResetColor();
                        Console.WriteLine("Pressione qualquer tecla para fechar esta janela...");
                        Console.ReadKey();
                    }
                    return exitCode;
                }
            }
            catch (Exception ex)
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine(string.Format("\n[ERRO CRÍTICO] {0}", ex.Message));
                Console.ResetColor();
                Console.WriteLine("Pressione qualquer tecla para fechar esta janela...");
                Console.ReadKey();
                return 1;
            }
        }

        static string FindPythonExecutable()
        {
            // 1. Check known local path for Python 3.14
            string localAppPython = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                @"Python\pythoncore-3.14-64\python.exe"
            );
            if (File.Exists(localAppPython)) return localAppPython;

            // 2. Check standard Programs/Python
            string programsPython = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                @"Programs\Python\Python314\python.exe"
            );
            if (File.Exists(programsPython)) return programsPython;

            // 3. Check python in PATH
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo("where.exe", "python.exe")
                {
                    RedirectStandardOutput = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };
                using (Process p = Process.Start(psi))
                {
                    string output = p.StandardOutput.ReadLine();
                    p.WaitForExit();
                    if (!string.IsNullOrEmpty(output) && File.Exists(output.Trim()))
                    {
                        return output.Trim();
                    }
                }
            }
            catch { }

            // 4. Fallback to "python.exe"
            return "python.exe";
        }
    }
}
