import React from 'react';
import {diffLines, formatLines} from 'unidiff';
import {parseDiff, Diff, Hunk} from 'react-diff-view';
import 'react-diff-view/style/index.css';


const renderFile = ({oldRevision, newRevision, type, hunks}) => (
    <Diff key={oldRevision + '-' + newRevision} viewType="split" diffType={type}
          hunks={hunks}>
        {hunks => hunks.map(hunk => <Hunk key={hunk.content} hunk={hunk}/>)}
    </Diff>
);
export default function DiffViewer({oldValue, newValue}) {
    const diffText = formatLines(diffLines(oldValue, newValue), {context: 3});
    const files = parseDiff(diffText);
    return <div>{files.map(renderFile)}</div>
}
