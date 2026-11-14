// Headless: list functions calling a target symbol, ranked by number of call sites.
// Args: <outFile> <symbolSubstring>
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.util.*;

public class CallersOf extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        PrintWriter out = new PrintWriter(new FileWriter(args[0]));
        String needle = args[1];
        // find matching symbols (functions)
        List<Function> targets = new ArrayList<>();
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            if (f.getName(true).contains(needle)) targets.add(f);
        }
        out.println("// targets matching '" + needle + "': " + targets.size());
        Map<Function,Integer> counts = new HashMap<>();
        for (Function t : targets) {
            out.println("//   target " + t.getName() + " @" + t.getEntryPoint());
            for (Reference ref : getReferencesTo(t.getEntryPoint())) {
                if (!ref.getReferenceType().isCall() && !ref.getReferenceType().isData()) continue;
                Function c = getFunctionContaining(ref.getFromAddress());
                if (c == null) continue;
                counts.merge(c, 1, Integer::sum);
            }
        }
        List<Map.Entry<Function,Integer>> es = new ArrayList<>(counts.entrySet());
        es.sort((a,b) -> b.getValue() - a.getValue());
        out.println("// callers ranked:");
        int n = 0;
        for (Map.Entry<Function,Integer> e : es) {
            out.println(String.format("%4d  %s @ %s  size=%d", e.getValue(), e.getKey().getName(),
                e.getKey().getEntryPoint(), e.getKey().getBody().getNumAddresses()));
            if (++n > 40) break;
        }
        out.close();
    }
}
