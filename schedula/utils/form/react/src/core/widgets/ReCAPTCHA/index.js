import React, {Suspense} from "react";

const Field = React.lazy(() => import('./core'));

export default function ReCAPTCHAWidget(props) {
    return <Suspense key={props.key}><Field{...props}/></Suspense>
}