#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import {
  opendir,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import path from "node:path";

type DriveInfo = {
  DeviceID: string;
  VolumeName?: string | null;
  FileSystem?: string | null;
  Size?: number | null;
  FreeSpace?: number | null;
};

type Args = {
  driveLetters: string[];
  toleranceSeconds: number;
  scanExisting: boolean;
  maxFiles: number;
  keepProbe: boolean;
  help: boolean;
};

type ProbeResult = {
  status: "OK" | "WARN" | "BAD";
  probePath: string;
  before: Date;
  after: Date;
  fileWrite: Date;
  deltaFromMidpointMs: number;
};

type FileSample = {
  fullPath: string;
  mtime: Date;
};

type ExistingScan = {
  count: number;
  futureCount: number;
  oldCount: number;
  newest?: FileSample;
  oldest?: FileSample;
  futureSamples: FileSample[];
  oldSamples: FileSample[];
};

const BEIJING_TIME_ZONE = "Asia/Shanghai";

function parseArgs(argv: string[]): Args {
  const args: Args = {
    driveLetters: [],
    toleranceSeconds: 5,
    scanExisting: false,
    maxFiles: 2000,
    keepProbe: false,
    help: false,
  };

  for (let index = 0; index < argv.length; index++) {
    const arg = argv[index];
    const next = () => {
      const value = argv[++index];
      if (!value) throw new Error(`Missing value after ${arg}`);
      return value;
    };

    if (arg === "--help" || arg === "-h") {
      args.help = true;
    } else if (arg === "--drive" || arg === "--drives" || arg === "-d") {
      args.driveLetters.push(...next().split(",").map(normalizeDriveId));
    } else if (arg === "--tolerance-seconds" || arg === "--tolerance") {
      args.toleranceSeconds = Number(next());
    } else if (arg === "--scan-existing") {
      args.scanExisting = true;
    } else if (arg === "--max-files") {
      args.maxFiles = Number(next());
    } else if (arg === "--keep-probe") {
      args.keepProbe = true;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  if (!Number.isFinite(args.toleranceSeconds) || args.toleranceSeconds < 0) {
    throw new Error("--tolerance-seconds must be a non-negative number");
  }
  if (!Number.isInteger(args.maxFiles) || args.maxFiles < 1) {
    throw new Error("--max-files must be a positive integer");
  }

  return args;
}

function printHelp() {
  console.log(`
SD card timestamp checker (Beijing time)

Usage:
  node tools/check-sd-card-time.ts
  node tools/check-sd-card-time.ts --drive E,F --scan-existing --keep-probe

Options:
  -d, --drive <E,F>          Only check these drive letters.
  --tolerance-seconds <n>    Allowed probe timestamp drift. Default: 5.
  --scan-existing            Sample existing files for future/ancient dates.
  --max-files <n>            Existing-file scan limit. Default: 2000.
  --keep-probe               Keep the tiny probe file on each card.
  -h, --help                 Show this help.

Notes:
  SD cards normally do not have their own clock. This checks whether new file
  timestamps on removable storage match current Beijing time as Windows reports it.
`);
}

function normalizeDriveId(value: string): string {
  const trimmed = value.trim().replace(/[\\/]+$/, "");
  if (/^[a-z]$/i.test(trimmed)) return `${trimmed.toUpperCase()}:`;
  return trimmed.toUpperCase();
}

function formatBeijing(date: Date): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: BEIJING_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  })
    .formatToParts(date)
    .reduce<Record<string, string>>((acc, part) => {
      if (part.type !== "literal") acc[part.type] = part.value;
      return acc;
    }, {});

  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second} +08:00`;
}

function formatLocal(date: Date): string {
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function formatUtc(date: Date): string {
  return `${date.toISOString().replace("T", " ").replace("Z", "")}Z`;
}

function formatDelta(ms: number): string {
  const seconds = Math.round((ms / 1000) * 1000) / 1000;
  return `${seconds >= 0 ? "+" : ""}${seconds} s`;
}

function formatGb(bytes?: number | null): string {
  if (!bytes) return "unknown";
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

function runPowerShellJson(command: string): unknown {
  const result = spawnSync(
    "powershell.exe",
    ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
    { encoding: "utf8" },
  );

  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(result.stderr.trim() || "PowerShell command failed");
  }

  const output = result.stdout.trim();
  if (!output) return [];
  return JSON.parse(output);
}

function asArray<T>(value: T | T[]): T[] {
  return Array.isArray(value) ? value : [value];
}

function getRemovableDrives(): DriveInfo[] {
  const command = [
    "Get-CimInstance Win32_LogicalDisk",
    "Where-Object { $_.DriveType -eq 2 -and $_.DeviceID }",
    "Select-Object DeviceID,VolumeName,FileSystem,Size,FreeSpace",
    "ConvertTo-Json -Compress",
  ].join(" | ");

  const parsed = runPowerShellJson(command);
  return asArray(parsed as DriveInfo | DriveInfo[]);
}

function getVisibleFileSystemDrives(): string[] {
  const command = [
    "Get-PSDrive -PSProvider FileSystem",
    "Select-Object Name",
    "ConvertTo-Json -Compress",
  ].join(" | ");
  const parsed = runPowerShellJson(command);
  return asArray(parsed as { Name: string } | { Name: string }[])
    .map((drive) => normalizeDriveId(drive.Name))
    .sort();
}

function getDrivesFromLetters(wanted: string[]): DriveInfo[] {
  return wanted.map((letter) => ({ DeviceID: normalizeDriveId(letter) }));
}

async function testProbeTimestamp(
  root: string,
  toleranceSeconds: number,
  keepProbe: boolean,
): Promise<ProbeResult> {
  const probePath = path.join(root, `.sd_time_probe_${randomUUID().replaceAll("-", "")}.txt`);
  const before = new Date();

  await writeFile(
    probePath,
    [
      "SD time probe",
      `UTC before write:     ${formatUtc(before)}`,
      `Beijing before write: ${formatBeijing(before)}`,
      `Local before write:   ${formatLocal(before)}`,
    ].join("\n"),
    "utf8",
  );

  const fileStat = await stat(probePath);
  const after = new Date();
  const fileWrite = fileStat.mtime;
  const midpoint = (before.getTime() + after.getTime()) / 2;
  const deltaFromMidpointMs = fileWrite.getTime() - midpoint;
  const maxAbsSeconds = Math.max(
    Math.abs(fileWrite.getTime() - before.getTime()),
    Math.abs(fileWrite.getTime() - after.getTime()),
  ) / 1000;

  const status =
    maxAbsSeconds <= toleranceSeconds ? "OK" : maxAbsSeconds <= 120 ? "WARN" : "BAD";

  if (!keepProbe) {
    await rm(probePath, { force: true });
  }

  return {
    status,
    probePath,
    before,
    after,
    fileWrite,
    deltaFromMidpointMs,
  };
}

async function* walkFiles(root: string): AsyncGenerator<string> {
  const stack = [root];

  while (stack.length > 0) {
    const current = stack.pop()!;
    let dir;
    try {
      dir = await opendir(current);
    } catch {
      continue;
    }

    for await (const entry of dir) {
      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        stack.push(fullPath);
      } else if (entry.isFile()) {
        yield fullPath;
      }
    }
  }
}

async function scanExistingTimestamps(root: string, maxFiles: number): Promise<ExistingScan> {
  const now = Date.now();
  const oldCutoff = Date.UTC(2000, 0, 1);
  const futureCutoff = now + 24 * 60 * 60 * 1000;
  const scan: ExistingScan = {
    count: 0,
    futureCount: 0,
    oldCount: 0,
    futureSamples: [],
    oldSamples: [],
  };

  for await (const fullPath of walkFiles(root)) {
    if (scan.count >= maxFiles) break;

    let fileStat;
    try {
      fileStat = await stat(fullPath);
    } catch {
      continue;
    }

    const sample = { fullPath, mtime: fileStat.mtime };
    const time = sample.mtime.getTime();
    scan.count++;

    if (!scan.newest || time > scan.newest.mtime.getTime()) scan.newest = sample;
    if (!scan.oldest || time < scan.oldest.mtime.getTime()) scan.oldest = sample;

    if (time > futureCutoff) {
      scan.futureCount++;
      if (scan.futureSamples.length < 5) scan.futureSamples.push(sample);
    }
    if (time < oldCutoff) {
      scan.oldCount++;
      if (scan.oldSamples.length < 5) scan.oldSamples.push(sample);
    }
  }

  return scan;
}

function warn(message: string) {
  console.warn(`WARNING: ${message}`);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    return;
  }

  const now = new Date();
  console.log("");
  console.log("=== SD card timestamp check ===");
  console.log(`Current UTC:      ${formatUtc(now)}`);
  console.log(`Current Beijing:  ${formatBeijing(now)}`);
  console.log(`Local timezone:   ${Intl.DateTimeFormat().resolvedOptions().timeZone || "unknown"}`);

  const timezoneOffsetMinutes = new Date().getTimezoneOffset();
  if (timezoneOffsetMinutes !== -480) {
    warn("This computer is not currently using UTC+08:00. Explorer local timestamps may not display as Beijing time.");
  }

  let drives: DriveInfo[];
  if (args.driveLetters.length > 0) {
    drives = getDrivesFromLetters(args.driveLetters);
  } else {
    try {
      drives = getRemovableDrives();
    } catch (error) {
      const available = getVisibleFileSystemDrives();
      warn("Automatic removable-drive detection is blocked by Windows permissions on this machine.");
      warn(`Visible file-system drives: ${available.join(", ") || "(none)"}`);
      warn("Run again with explicit drive letters, for example: node tools/check-sd-card-time.ts --drive E,F");
      process.exitCode = 2;
      return;
    }
  }

  if (drives.length === 0) {
    warn("No matching removable drives were found. Insert the SD card or pass --drive E where E is the card drive.");
    process.exitCode = 2;
    return;
  }

  for (const drive of drives) {
    const root = `${normalizeDriveId(drive.DeviceID)}\\`;
    console.log("");
    console.log(`--- Drive ${drive.DeviceID} ---`);
    console.log(`Volume:           ${drive.VolumeName || "(no label)"}`);
    console.log(`File system:      ${drive.FileSystem || "unknown"}`);
    console.log(`Size/free:        ${formatGb(drive.Size)} / ${formatGb(drive.FreeSpace)}`);

    try {
      await stat(root);
      const probe = await testProbeTimestamp(root, args.toleranceSeconds, args.keepProbe);
      console.log(`Probe status:     ${probe.status}`);
      console.log(`Probe delta:      ${formatDelta(probe.deltaFromMidpointMs)}`);
      console.log(`File write BJT:   ${formatBeijing(probe.fileWrite)}`);
      console.log(`File write local: ${formatLocal(probe.fileWrite)}`);
      if (args.keepProbe) console.log(`Probe kept at:    ${probe.probePath}`);

      if (probe.status === "OK") {
        console.log("Result:           New file timestamps match current Beijing time within tolerance.");
      } else if (probe.status === "WARN") {
        warn("New file timestamp is slightly off. FAT/exFAT timestamp granularity or slow media can cause small differences.");
      } else {
        warn("New file timestamp is far from current time. Check Windows time/time zone, reader behavior, or the device that writes files to this card.");
      }

      if (args.scanExisting) {
        const scan = await scanExistingTimestamps(root, args.maxFiles);
        console.log(`Scanned files:    ${scan.count} (limit ${args.maxFiles})`);

        if (scan.newest) {
          console.log(`Newest file:      ${formatBeijing(scan.newest.mtime)}  ${scan.newest.fullPath}`);
        }
        if (scan.oldest) {
          console.log(`Oldest file:      ${formatBeijing(scan.oldest.mtime)}  ${scan.oldest.fullPath}`);
        }

        if (scan.futureCount > 0) {
          warn(`Existing-file check found ${scan.futureCount} file(s) more than 1 day in the future.`);
          for (const sample of scan.futureSamples) {
            console.log(`  FUTURE ${formatBeijing(sample.mtime)}  ${sample.fullPath}`);
          }
        }
        if (scan.oldCount > 0) {
          warn(`Existing-file check found ${scan.oldCount} file(s) before 2000-01-01.`);
          for (const sample of scan.oldSamples) {
            console.log(`  OLD    ${formatBeijing(sample.mtime)}  ${sample.fullPath}`);
          }
        }
        if (scan.futureCount === 0 && scan.oldCount === 0) {
          console.log("Existing files:   No obvious future/ancient timestamps in sampled files.");
        }
      }
    } catch (error) {
      warn(`Failed to test ${drive.DeviceID}: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  console.log("");
  console.log("Done.");
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
