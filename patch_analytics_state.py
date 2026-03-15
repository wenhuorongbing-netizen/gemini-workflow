import sys

with open('app/page.tsx', 'r') as f:
    content = f.read()

replacement = '''  const [currentUserId, setCurrentUserId] = useState<string>("user1");
  const [userStats, setUserStats] = useState<any>(null);

  useEffect(() => {
    const savedUserId = localStorage.getItem('current_userId');
    if (savedUserId) setCurrentUserId(savedUserId);
  }, []);

  useEffect(() => {
    localStorage.setItem('current_userId', currentUserId);
    fetchWorkspaces();
    fetchUserStats();
  }, [currentUserId]);

  const fetchUserStats = async () => {
      try {
          const res = await fetch('/api/user', { headers: { 'x-user-id': currentUserId } });
          if (res.ok) setUserStats(await res.json());
      } catch(e) {}
  };'''

target = '''  const [currentUserId, setCurrentUserId] = useState<string>("user1");

  useEffect(() => {
    const savedUserId = localStorage.getItem('current_userId');
    if (savedUserId) setCurrentUserId(savedUserId);
  }, []);

  useEffect(() => {
    localStorage.setItem('current_userId', currentUserId);
    fetchWorkspaces();
  }, [currentUserId]);'''

content = content.replace(target, replacement)

with open('app/page.tsx', 'w') as f:
    f.write(content)
