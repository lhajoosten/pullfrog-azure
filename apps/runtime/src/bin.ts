import { runCommand } from "./command.js";

process.exitCode = runCommand(process.argv.slice(2), process.env, {
  stdout: (message) => process.stdout.write(message),
  stderr: (message) => process.stderr.write(message),
});
