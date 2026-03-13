import { RouterProvider } from 'react-router';
import { router } from './routes.js';

export default function App() {
  return <RouterProvider router={router} />;
}