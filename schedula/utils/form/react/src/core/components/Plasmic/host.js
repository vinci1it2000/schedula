import {PlasmicCanvasHost} from '@plasmicapp/loader-react';

const PlasmicHOST = ({children, render, ...props}) => (
    <PlasmicCanvasHost {...props}>
        {children}
    </PlasmicCanvasHost>);
export default PlasmicHOST;