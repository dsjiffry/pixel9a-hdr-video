// Headless: create functions at every address listed (hex, one per line, file offsets) + image base.
// Args: <addrFile>
import ghidra.app.script.GhidraScript;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import java.io.*;
import java.nio.file.*;

public class CreateFns extends GhidraScript {
    @Override
    public void run() throws Exception {
        long base = currentProgram.getImageBase().getOffset();
        int made = 0, had = 0, fail = 0;
        for (String l : Files.readAllLines(new File(getScriptArgs()[0]).toPath())) {
            l = l.strip(); if (l.isEmpty()) continue;
            Address a = toAddr(base + Long.decode(l));
            if (getFunctionAt(a) != null) { had++; continue; }
            if (getInstructionAt(a) == null) new DisassembleCommand(a, null, true).applyTo(currentProgram, monitor);
            Function f = createFunction(a, null);
            if (f != null) made++; else fail++;
        }
        println("existing=" + had + " created=" + made + " failed=" + fail);
    }
}
