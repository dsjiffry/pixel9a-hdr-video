// Headless: decompile every function (in parallel) and write those whose C text matches a regex.
// Args: <outFile> <regex>
import ghidra.app.decompiler.*;
import ghidra.app.decompiler.parallel.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.util.task.TaskMonitor;
import java.io.*;
import java.util.*;
import java.util.regex.*;

public class GrepDecomp extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String rx = args[1].startsWith("@")
            ? java.nio.file.Files.readString(new File(args[1].substring(1)).toPath()).strip() : args[1];
        final Pattern pat = Pattern.compile(rx);
        final PrintWriter out = new PrintWriter(new FileWriter(args[0]));
        DecompileConfigurer cfg = d -> {
            DecompileOptions o = new DecompileOptions();
            d.setOptions(o); d.toggleCCode(true); d.toggleSyntaxTree(false);
            d.setSimplificationStyle("decompile");
        };
        List<Function> fns = new ArrayList<>();
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) if (!f.isThunk() && !f.isExternal()) fns.add(f);
        println("functions: " + fns.size());
        DecompilerCallback<String> dcb = new DecompilerCallback<>(currentProgram, cfg) {
            @Override
            public String process(DecompileResults r, TaskMonitor m) {
                if (r == null || !r.decompileCompleted()) return null;
                String c = r.getDecompiledFunction().getC();
                Matcher mm = pat.matcher(c);
                if (!mm.find()) return null;
                return "//==== " + r.getFunction().getName() + " @ " + r.getFunction().getEntryPoint() + " match=" + mm.group() + "\n" + c;
            }
        };
        dcb.setTimeout(60);
        List<String> res = ParallelDecompiler.decompileFunctions(dcb, fns, monitor);
        dcb.dispose();
        int n = 0;
        for (String s : res) if (s != null) { out.println(s); n++; }
        out.close();
        println("matches: " + n);
    }
}
