import React, {Suspense} from "react";

const Button = React.lazy(() => import('@mui/material/Button'));

export default function _submit(props) {
    return (<Suspense><Button key="submit" type="submit" {...props}>
            {props.children || "submit"}
        </Button></Suspense>
    );
}