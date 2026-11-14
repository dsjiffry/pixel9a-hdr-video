// Headless: dump a function's entry, instructions (addr, bytes, text), and return/branch sites.
// Args: <outFile> <addr>
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.util.NumericUtilities;
import java.io.*;

public class DumpFn extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        PrintWriter out = new PrintWriter(new FileWriter(args[0]));
        Address a = toAddr(args[1]);
        Function f = getFunctionContaining(a);
        if (f == null) { out.println("no function at " + args[1]); out.close(); return; }
        out.println("entry=" + f.getEntryPoint() + " name=" + f.getName() + " body=" + f.getBody());
        Listing lst = currentProgram.getListing();
        InstructionIterator it = lst.getInstructions(f.getBody(), true);
        while (it.hasNext()) {
            Instruction ins = it.next();
            byte[] b = ins.getBytes();
            out.println(ins.getAddress() + "  " + NumericUtilities.convertBytesToString(b, " ") + "   " + ins.toString());
        }
        out.close();
    }
}
