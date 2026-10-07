using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Windows.Forms;

internal static class SetupLauncher
{
    private const long RequiredFreeBytes = 3L * 1024 * 1024 * 1024;

    [STAThread]
    private static void Main()
    {
        string appHome = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Programs", "QostanaiProctor");

        try
        {
            var drive = new DriveInfo(Path.GetPathRoot(appHome));
            if (drive.AvailableFreeSpace < RequiredFreeBytes)
                throw new InvalidOperationException(
                    "На диске C: мало места. Освободите не менее 3 ГБ и запустите установщик снова.");

            string root = Path.GetFullPath(appHome) + Path.DirectorySeparatorChar;
            using (Stream payload = Assembly.GetExecutingAssembly()
                .GetManifestResourceStream("QostanaiProctor.zip"))
            using (var archive = new ZipArchive(payload, ZipArchiveMode.Read))
            {
                foreach (ZipArchiveEntry entry in archive.Entries)
                {
                    string relativePath = entry.FullName.Replace('/', Path.DirectorySeparatorChar);
                    string destination = Path.GetFullPath(Path.Combine(root, relativePath));
                    if (!destination.StartsWith(root, StringComparison.OrdinalIgnoreCase))
                        throw new InvalidDataException("Архив содержит недопустимый путь.");

                    if (entry.FullName.EndsWith("/", StringComparison.Ordinal))
                    {
                        Directory.CreateDirectory(destination);
                        continue;
                    }

                    Directory.CreateDirectory(Path.GetDirectoryName(destination));
                    using (Stream input = entry.Open())
                    using (Stream output = File.Create(destination))
                        input.CopyTo(output);
                }
            }

            string appPath = Path.Combine(appHome, "QostanaiProctor.exe");
            if (!File.Exists(appPath))
                throw new FileNotFoundException("Не удалось распаковать программу.");

            CreateShortcut(
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
                    "Qostanai Proctor.lnk"), appPath, appHome);

            string startMenu = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.Programs), "Qostanai Proctor");
            Directory.CreateDirectory(startMenu);
            CreateShortcut(Path.Combine(startMenu, "Qostanai Proctor.lnk"), appPath, appHome);
            Process.Start(new ProcessStartInfo(appPath) { WorkingDirectory = appHome });
        }
        catch (Exception error)
        {
            MessageBox.Show(error.Message, "Установка Qostanai Proctor",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private static void CreateShortcut(string shortcutPath, string appPath, string workingDirectory)
    {
        Type shellType = Type.GetTypeFromProgID("WScript.Shell");
        object shell = Activator.CreateInstance(shellType);
        object shortcut = shellType.InvokeMember("CreateShortcut",
            BindingFlags.InvokeMethod, null, shell, new object[] { shortcutPath });
        Type shortcutType = shortcut.GetType();
        shortcutType.InvokeMember("TargetPath", BindingFlags.SetProperty,
            null, shortcut, new object[] { appPath });
        shortcutType.InvokeMember("WorkingDirectory", BindingFlags.SetProperty,
            null, shortcut, new object[] { workingDirectory });
        shortcutType.InvokeMember("Save", BindingFlags.InvokeMethod, null, shortcut, null);
    }
}
