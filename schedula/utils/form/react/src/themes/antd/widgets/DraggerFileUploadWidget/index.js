import React, {Suspense} from "react";

const Field = React.lazy(() => import('./core'));

export default function DraggerFileUploadWidget(props) {
    return <Suspense key={props.key}><Field{...props}/></Suspense>
}