import React from 'react';
import {Viewer, Differ} from 'json-diff-kit';
import 'json-diff-kit/dist/viewer.css';

export default function DiffViewer({oldValue, newValue}) {
    const differ = new Differ({
        detectCircular: true,    // default `true`
        maxDepth: Infinity,      // default `Infinity`
        showModifications: true, // default `true`
        arrayDiffMethod: 'lcs',  // default `"normal"`, but `"lcs"` may be more useful
    });

// you may want to use `useMemo` (for React) or `computed` (for Vue)
// to avoid redundant computations
    const diff = differ.diff(oldValue, newValue);
    return <Viewer
        diff={diff}          // required
        indent={4}                 // default `2`
        lineNumbers={true}         // default `false`
        hideUnchangedLines={true}
        highlightInlineDiff={true} // default `false`
        inlineDiffOptions={{
            mode: 'word',            // default `"char"`, but `"word"` may be more useful
            wordSeparator: ' ',      // default `""`, but `" "` is more useful for sentences
        }}
    />
}
