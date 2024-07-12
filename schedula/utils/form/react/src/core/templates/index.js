import React from "react";

const ContentProvider = React.lazy(() => import('./ContentProvider'));

export function generateTemplates() {
    return {
        ContentProvider
    }
}

export default generateTemplates();
