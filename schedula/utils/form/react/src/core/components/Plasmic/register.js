import {usePlasmicStore} from "../../models/plasmic";

const PlasmicRegister = ({children, render, components, ...props}) => {
    const {registerComponents} = usePlasmicStore()
    registerComponents(render, components)
    return children
}
export default PlasmicRegister;