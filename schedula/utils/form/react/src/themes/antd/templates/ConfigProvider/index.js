import React, {Suspense} from "react";

const Component = React.lazy(() => import('./core'));

export default function ConfigProvider(props) {
    return <Suspense><Component{...props}/></Suspense>

}