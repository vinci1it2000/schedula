import {usePlasmicStore} from "../../../models/plasmic";

const PlasmicRegisterComponents = ({children, render, components, ...props}) => {
    const {registerComponents} = usePlasmicStore()
    registerComponents(render, components)
    return children
}
export default PlasmicRegisterComponents;