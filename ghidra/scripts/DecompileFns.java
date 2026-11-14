// Headless: decompile functions to a text file.
// Args: <outFile> <addr|name> [<addr|name> ...]
// An argument of the form "callees:<addr>" also decompiles every direct callee of that function (one level).
// An argument of the form "strref:<text>" decompiles every function referencing a defined string containing <text>.
import ghidra.app.decompiler.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.data.StringDataInstance;
import java.io.*;
import java.util.*;

public class DecompileFns extends GhidraScript {
    private DecompInterface ifc;
    private PrintWriter out;
    private Set<Address> done = new HashSet<>();

    private Function resolve(String s) {
        try {
            Address a = toAddr(s);
            Function f = getFunctionContaining(a);
            if (f == null) {
                disassemble(a);
                f = createFunction(a, null);
            }
            return f;
        } catch (Exception e) {
            List<Function> fs = getGlobalFunctions(s);
            return fs.isEmpty() ? null : fs.get(0);
        }
    }

    private void emit(Function f) {
        if (f == null || !done.add(f.getEntryPoint())) return;
        DecompileResults r = ifc.decompileFunction(f, 180, monitor);
        out.println("//==== " + f.getName() + " @ " + f.getEntryPoint() + " size=" + f.getBody().getNumAddresses());
        if (r != null && r.decompileCompleted()) out.println(r.getDecompiledFunction().getC());
        else out.println("// decompile failed: " + (r == null ? "null" : r.getErrorMessage()));
        out.flush();
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        // "@listfile": first line = output file, each further line = one target (lets targets contain spaces).
        if (args.length == 1 && args[0].startsWith("@")) {
            List<String> l = new ArrayList<>();
            for (String s : java.nio.file.Files.readAllLines(new File(args[0].substring(1)).toPath()))
                if (!s.isBlank()) l.add(s.strip());
            args = l.toArray(new String[0]);
        }
        out = new PrintWriter(new FileWriter(args[0]));
        ifc = new DecompInterface();
        DecompileOptions opt = new DecompileOptions();
        ifc.setOptions(opt);
        ifc.toggleCCode(true);
        ifc.openProgram(currentProgram);
        for (int i = 1; i < args.length; i++) {
            String a = args[i];
            if (a.startsWith("callees:")) {
                Function f = resolve(a.substring(8));
                emit(f);
                if (f != null) for (Function c : f.getCalledFunctions(monitor)) if (!c.isThunk() && !c.isExternal()) emit(c);
            } else if (a.startsWith("text:")) {
                // find raw bytes of the text in memory, then every function with a reference into that string
                byte[] pat = a.substring(5).getBytes("ISO-8859-1");
                Address hit = currentProgram.getMinAddress();
                while ((hit = currentProgram.getMemory().findBytes(hit, pat, null, true, monitor)) != null) {
                    Address start = hit;   // walk back to the start of the C string
                    while (true) {
                        Address p = start.subtract(1);
                        byte b = currentProgram.getMemory().getByte(p);
                        if (b == 0) break;
                        start = p;
                    }
                    for (Address x = start; x.compareTo(hit.add(pat.length)) <= 0; x = x.add(1))
                        for (Reference ref : getReferencesTo(x)) {
                            Function f = getFunctionContaining(ref.getFromAddress());
                            out.println("// text '" + a.substring(5) + "' @" + start + " ref from " + ref.getFromAddress() + " in " + (f == null ? "?" : f.getName()));
                            emit(f);
                        }
                    hit = hit.add(1);
                }
            } else if (a.startsWith("strref:")) {
                String needle = a.substring(7);
                DataIterator it = currentProgram.getListing().getDefinedData(true);
                while (it.hasNext()) {
                    Data d = it.next();
                    if (!d.hasStringValue()) continue;
                    String v = StringDataInstance.getStringDataInstance(d).getStringValue();
                    if (v == null || !v.contains(needle)) continue;
                    for (Reference ref : getReferencesTo(d.getAddress())) {
                        Function f = getFunctionContaining(ref.getFromAddress());
                        if (f != null) { out.println("// strref '" + v + "' from " + ref.getFromAddress()); emit(f); }
                    }
                }
            } else {
                emit(resolve(a));
            }
        }
        out.close();
        ifc.dispose();
    }
}
