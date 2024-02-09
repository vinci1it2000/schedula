import React, {Suspense} from "react";

const Field = React.lazy(() => import('./core'));

export default function MentionsWidget(props) {
    return <Suspense key={props.key}><Field{...props}/></Suspense>
}