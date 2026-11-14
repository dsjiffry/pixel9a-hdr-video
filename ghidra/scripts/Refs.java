// Headless: walk references to one or more addresses, up to N hops, print containing functions.
// Args: <outFile> <hops> <addr> [<addr> ...]
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.util.*;

public class Refs extends GhidraScript {
    PrintWriter out;
    Set<Long> seen = new HashSet<>();

    void walk(Address a, int hopsLeft, String path) {
        if (a == null) return;
        if (!seen.add(a.getOffset() | ((long)hopsLeft << 48))) return;
        for (Reference ref : getReferencesTo(a)) {
            Address from = ref.getFromAddress();
            Function f = getFunctionContaining(from);
            String rt = ref.getReferenceType().toString();
            String where = (f == null) ? ("data " + from) : (f.getName() + " @" + f.getEntryPoint() + " (from " + from + ")");
            out.println(path + " <- [" + rt + "] " + where);
            if (f == null && hopsLeft > 0) {
                // reference comes from a data location (e.g. a pointer slot); keep walking up
                walk(from, hopsLeft - 1, path + "  ");
            }
        }
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        out = new PrintWriter(new FileWriter(args[0]));
        int hops = Integer.parseInt(args[1]);
        for (int i = 2; i < args.length; i++) {
            Address a = toAddr(args[i]);
            out.println("==== refs to " + args[i] + " ====");
            walk(a, hops, args[i]);
        }
        out.close();
    }
}
