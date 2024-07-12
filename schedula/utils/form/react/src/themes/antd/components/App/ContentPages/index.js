import React from "react";
import PlasmicPage from "../../../../../core/components/Plasmic/page";

export default function Page({homePath, render, ...props}) {
    return <PlasmicPage render={render} homePath={homePath} {...props}/>
}
